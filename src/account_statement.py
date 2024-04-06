import re
from dataclasses import dataclass, field
from typing import ClassVar
import fitz
from src.transactions import Transaction
from src.constants import TransactionConstants
from src.transactions import IncomingPayment, ElectronicBankingTransfer
from src.transactions import OutgoingPaymentDomestic, OutgoingPaymentPeriodic
from src.transactions import CardPaymentDebit, CardAtmCashOut, CardPaymentIncoming
from src.transactions import BankPayedService, DirectDebit
from src.transactions import InterestPositive, TaxInterest


@dataclass
class StatementAccount:
    """Class representing a bank account statement in PDF."""

    all: ClassVar[list["StatementAccount"]] = []
    """Class attribute to hold all created instances of StatementAccount."""
    file_path: str
    "Path to the statement PDF file."
    bank_name: str = field(default=None)
    "Bank name of the statement."
    account_number: str = field(default=None)
    "Bank account number of the statement."
    year: int = field(default=None)
    "Year of the statement."
    start_balance: float = field(default=None)
    "Account balance at the start of the account statement."
    end_balance: float = field(default=None)
    "Account balance at the end of the account statement."
    pages_content: list[list[str]] = field(default_factory=list)
    "All the pages of the statement, each page is list of string. Defaults to empty list."
    all_transactions: list[Transaction] = field(default_factory=list)
    "All the transactions from this Statement."

    def __post_init__(self):
        self.extract_pages_text()
        self.get_bank_name()
        self.get_account_nr()
        self.get_account_start_balance()
        self.get_account_end_balance()
        self.get_statement_year()
        self.get_transactions()
        StatementAccount.all.append(self)

    def extract_pages_text(self) -> None:
        """Get all the text from all Statement pages.

        Store all the pages and their text content in pages_content attribute.
        """
        statement = fitz.open(self.file_path)
        for page in statement:
            page_content = page.get_text()
            text_lines = page_content.split("\n")
            self.pages_content.append(text_lines)

    def get_bank_name(self) -> None:
        """Get name of bank of given account statement."""

        bank_names = {
            "Československá obchodní banka, a. s.,": "csob",
            "Česká spořitelna, a.s.,": "cs",
            "Plus účet České spořitelny": "cs",
            "Revolut": "revolut",
        }
        for page_lines in self.pages_content:
            for line in page_lines:
                for key in bank_names:
                    if key in line:
                        self.bank_name = bank_names.get(key)
                        return

    def get_account_nr(self) -> None:
        """Get the account number of given pdf statement."""

        for page_lines in self.pages_content:
            for i, line in enumerate(page_lines):
                if "Číslo účtu/kód banky:" in line:  # CS rule.
                    self.account_number = line.replace("Číslo účtu/kód banky:", "").strip()
                    return
                elif line.strip() == "Účet:":  # CSOB rule.
                    self.account_number = page_lines[i + 1].strip()
                    return
                elif re.match(r"^LT\d*$", line.strip()) and "REVOLT21" in page_lines[i + 1]:  # Revolut rule.
                    self.account_number = line.strip()
                    return

    def get_account_start_balance(self) -> None:
        """Get the account balance at the start of given Statement."""

        for page_lines in self.pages_content:
            for i, line in enumerate(page_lines):
                if "Počáteční zůstatek:" in line and self.bank_name in ["csob", "cs"]:  # CS + CSOB rule
                    amount_text = page_lines[i + 1]
                    self.start_balance = round(
                        float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2
                    )
                    return
                elif "Souhrn zůstatku" in line and self.bank_name == "revolut":  # Revolut rule CZ
                    for o, line in enumerate(page_lines[i:]):
                        if line.strip() == "Celkem":
                            amount_text = page_lines[i + o + 1]  # End balance should be 1st line after "Celkem:" line.
                            self.start_balance = round(float(amount_text.replace(" CZK", "").replace(",", "")), 2)
                            return

    def get_account_end_balance(self) -> None:
        """Get the account balance at the end of given Statement."""

        if self.bank_name == "revolut":  # Revolut rule CZ
            # There can be multiple summary sections and each regarding only part of the month.
            # So we need to find the last summary section of all pages to get month end balance.
            last_summary_section_index = None
            for page_lines in self.pages_content:
                for i, line in enumerate(page_lines):
                    if "Souhrn zůstatku" in line:
                        last_summary_section_index = i
                for o, line in enumerate(page_lines[last_summary_section_index:]):
                    if line.strip() == "Celkem":
                        amount_text = page_lines[
                            last_summary_section_index + o + 4
                        ]  # End balance should be 4th line after "Celkem:" line.
                        self.end_balance = round(float(amount_text.replace(" CZK", "").replace(",", "")), 2)
                        return
        elif self.bank_name in ["csob", "cs"]:
            for page_lines in self.pages_content:
                for i, line in enumerate(page_lines):
                    if "Konečný zůstatek:" in line:
                        amount_text = page_lines[i + 1]
                        self.end_balance = round(
                            float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2
                        )
                        return

    def get_statement_year(self) -> None:
        """Get year of pdf statement."""

        for page_lines in self.pages_content:
            for i, line in enumerate(page_lines):
                if line.strip() == "Období:":  # CSOB rule
                    self.year = page_lines[i + 1].strip()[-4:]
                    return
                elif "Období:" in line.strip():  # CS rule
                    self.year = page_lines[i].strip()[-4:]
                    return
                elif "Transakce účtu od" in line:  # Revolut rule
                    self.year = line.strip()[-4:]
                    return

    def get_transactions(self) -> None:
        """Go through all the PDF file content and extract all the transactions from it.

        Check each line, if it contains start of any transaction type. If yes, create new Transaction instance.
        If not, add that line to content of current active Transaction.
        """
        is_transaction_lines_active = False
        for page in self.pages_content:
            # for i, line in enumerate(page):
            #    print(i, line)
            for i, line in enumerate(page):
                if any(identifier in line for identifier in CardPaymentIncoming.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = CardPaymentIncoming.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_to=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in IncomingPayment.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = IncomingPayment.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_to=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(
                    identifier in line for identifier in OutgoingPaymentDomestic.text_identifiers.get(self.bank_name)
                ):
                    is_transaction_lines_active = True
                    tx = OutgoingPaymentDomestic.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in CardPaymentDebit.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = CardPaymentDebit.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in CardAtmCashOut.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = CardAtmCashOut.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in BankPayedService.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = BankPayedService.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(
                    identifier in line for identifier in OutgoingPaymentPeriodic.text_identifiers.get(self.bank_name)
                ):
                    is_transaction_lines_active = True
                    tx = OutgoingPaymentPeriodic.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in InterestPositive.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = InterestPositive.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in TaxInterest.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = TaxInterest.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(
                    identifier in line for identifier in ElectronicBankingTransfer.text_identifiers.get(self.bank_name)
                ):
                    is_transaction_lines_active = True
                    tx = ElectronicBankingTransfer.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                elif any(identifier in line for identifier in DirectDebit.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = DirectDebit.create(
                        bank=self.bank_name,
                        year=self.year,
                        statement_account=self.account_number,
                        account_from=self.account_number,
                        line_index=i,
                        extracted_text_lines=page,
                    )
                    self.all_transactions.append(tx)
                    tx.parent_statement = self.file_path
                # In case the line contains any text, that indicates end of page / file → close current opened
                # Transaction.
                elif line in TransactionConstants.TRANSACTION_END_SECTION:
                    is_transaction_lines_active = False
                # In case no rule above was triggered → this is line belonging to currently opened Transaction. → Append
                # line to Transaction content.
                elif is_transaction_lines_active and line:
                    self.all_transactions[-1].all_transaction_lines_text += f"{line.strip()}\n"
