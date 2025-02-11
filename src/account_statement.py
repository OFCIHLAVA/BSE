import csv
import os
from dataclasses import dataclass, field
import re
from typing import ClassVar


import fitz

from src.helper_functions import get_date_from_string
from src.transactions import Transaction
from src.constants import TransactionConstants
from src.transactions import IncomingPayment, ElectronicBankingTransfer, CardAtmCashOut
from src.transactions import OutgoingPayment, OutgoingPaymentPeriodic
from src.transactions import CardPaymentDebit, CardAtmCashOut, CardPaymentIncoming, CardAtmDeposit
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
    pages_content_pdf: list[list[str]] = field(default_factory=list)
    """All the pages of the statement, each page is list of string. In case StatementAccount is created from pdf file.
    Defaults to empty list."""
    csv_content: list[dict] = field(default_factory=list)
    """All the data lines from csv represented by list of dictionaries. In case StatementAccount is created from csv 
    file. Defaults to empty list."""
    all_transactions: list[Transaction] = field(default_factory=list)
    "All the transactions from this Statement."

    def __post_init__(self):
        if self.file_path.lower().endswith(".pdf"):
            self.initialize_from_pdf()
        if self.file_path.lower().endswith(".csv"):
            self.initialize_from_csv()
        StatementAccount.all.append(self)

    def initialize_from_pdf(self):
        """Create StatementAccount instance from PDF file."""
        self.extract_pages_text_pdf()
        self.get_bank_name_pdf()
        self.get_account_nr_pdf()
        self.get_account_start_balance_pdf()
        self.get_account_end_balance_pdf()
        self.get_statement_year_pdf()
        self.get_transactions_pdf()

    def initialize_from_csv(self):
        """Create StatementAccount instance from csv file."""
        self.extract_data_csv()
        self.bank_name = "revolut"
        self.account_number = self.get_account_nr_csv()
        self.get_account_start_balance_csv()
        self.get_account_end_balance_csv()
        self.year = self.get_statement_year_csv()
        self.get_transactions_csv()

        # self.get_transactions_pdf()

    def extract_pages_text_pdf(self) -> None:
        """Get all the text from all Statement pages.

        Store all the pages and their text content in pages_content attribute.
        """
        statement = fitz.open(self.file_path)
        for page in statement:
            page_content = page.get_text()
            text_lines = page_content.split("\n")
            self.pages_content_pdf.append(text_lines)

    def extract_data_csv(self) -> None:
        """Load the csv data of gives statement."""

        with open(self.file_path, mode="r", encoding="utf-8") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                self.csv_content.append(row)

    def get_bank_name_pdf(self) -> None:
        """Get name of bank of given account statement."""

        bank_names = {
            "Československá obchodní banka, a. s.,": "csob",
            "Česká spořitelna, a.s.,": "cs",
            "Plus účet České spořitelny": "cs",
            "Revolut": "revolut",
        }
        for page_lines in self.pages_content_pdf:
            for line in page_lines:
                for key in bank_names:
                    if key in line:
                        self.bank_name = bank_names.get(key)
                        return

    def get_account_nr_pdf(self) -> None:
        """Get the account number of given pdf statement."""

        for page_lines in self.pages_content_pdf:
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

    def get_account_start_balance_pdf(self) -> None:
        """Get the account balance at the start of given Statement."""

        for page_lines in self.pages_content_pdf:
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

    def get_account_nr_csv(self) -> None:
        """Get the currency of given revolut csv statement."""
        currencies = {"CZK", "USD", "EUR"}
        revolut_account_nr = "LT443250037740989361"
        for c in currencies:
            if c in self.file_path.upper():
                return revolut_account_nr + c
        return ""

    def get_account_start_balance_csv(self) -> None:
        """Get the account balance at the start of given Statement."""

        if self.csv_content:
            first_line = self.csv_content[0]

            balance_after_1st_line = float(first_line.get("Balance"))
            amount_1st_line = float(first_line.get("Amount"))
            self.start_balance = balance_after_1st_line - amount_1st_line

    def get_account_end_balance_csv(self) -> None:
        """Get the account balance at the end of given Statement."""

        if self.csv_content:
            last_line = self.csv_content[-1]
            self.end_balance = float(last_line.get("Balance"))

    def get_account_end_balance_pdf(self) -> None:
        """Get the account balance at the end of given Statement."""

        if self.bank_name == "revolut":  # Revolut rule CZ
            # There can be multiple summary sections and each regarding only part of the month.
            # So we need to find the last summary section of all pages to get month end balance.
            last_summary_section_index = None
            for page_lines in self.pages_content_pdf:
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
            for page_lines in self.pages_content_pdf:
                for i, line in enumerate(page_lines):
                    if "Konečný zůstatek:" in line:
                        amount_text = page_lines[i + 1]
                        self.end_balance = round(
                            float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2
                        )
                        return

    def get_statement_year_pdf(self) -> None:
        """Get year of pdf statement."""

        for page_lines in self.pages_content_pdf:
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

    def get_statement_year_csv(self) -> None:
        """Get year of csv statement.

        # TODO - this is no longer true - remove this comment bellow
        Note:
            Year is extracted from filename. Filename should always be in format "cs2003", "eur2211", ... , where
            strings at the start indicates the currency of the Statement, first 2 digits means year and last 2 digits
            mean month.
        """
        # year_pattern: str = r"\D*(\d\d)"
        # match = re.search(year_pattern, self.file_path)
        # if match:
        #    year = "20" + match.group(1)
        #    return year
        # return 0

        # Split the file path into the base name and the extension
        base_name, extension = os.path.splitext(self.file_path)
        # Get the last two characters of the base name
        return "20" + base_name[-2:]

    def get_transactions_pdf(self) -> None:
        """Go through all the PDF file content and extract all the transactions from it.

        Check each line, if it contains start of any transaction type. If yes, create new Transaction instance.
        If not, add that line to content of current active Transaction.
        """
        is_transaction_lines_active = False
        for page in self.pages_content_pdf:
            for i, line in enumerate(page):
                print(i, line)
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
                elif any(identifier in line for identifier in OutgoingPayment.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = OutgoingPayment.create(
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
                elif any(identifier in line for identifier in CardAtmDeposit.text_identifiers.get(self.bank_name)):
                    is_transaction_lines_active = True
                    tx = CardAtmDeposit.create(
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

    def get_transactions_csv(self) -> None:
        """Extract all the transactions given StatementAccount csv_content."""
        revolut_rules = {
            OutgoingPayment: {
                "type": ["transfer", "exchange"],
                "negative": True,
            },
            IncomingPayment: {
                "type": ["transfer", "exchange", "topup"],
                "negative": False,
            },
            CardPaymentDebit: {
                "type": [
                    "card_payment",
                ],
                "negative": True,
            },
            CardPaymentIncoming: {
                "type": [
                    "card_payment",
                ],
                "negative": False,
            },
            BankPayedService: {
                "type": [
                    "fee",
                ],
                "negative": True,
            },
            CardAtmCashOut: {
                "type": [
                    "atm",
                ],
                "negative": True,
            },
        }

        for row in self.csv_content:
            tx_type = row.get("Type")
            date_started = (
                "ERROR - MISSING DATE" if not row.get("Started Date") else get_date_from_string(row.get("Started Date"))
            )
            date_completed = (
                "ERROR - MISSING DATE"
                if not row.get("Completed Date")
                else get_date_from_string(row.get("Completed Date"))
            )
            description = row.get("Description")
            amount = float(row.get("Amount"))
            fee = float(row.get("Fee"))
            currency = row.get("Currency")
            state = row.get("State")

            if not StatementAccount.is_transaction_valid(state):
                continue

            # Check for the rules
            # 1. type first
            for key, values in revolut_rules.items():
                if tx_type.lower() in values.get("type"):
                    if values.get("negative") == (amount < 0):
                        if key == OutgoingPayment:
                            tx = OutgoingPayment(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_from=self.account_number,
                                year=self.year,
                                amount=amount,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                            )
                        elif key == IncomingPayment:
                            tx = IncomingPayment(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_to=self.account_number,
                                year=self.year,
                                amount=amount,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                            )
                        elif key == CardPaymentDebit:
                            tx = CardPaymentDebit(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_from=self.account_number,
                                year=self.year,
                                amount=amount,
                                card_identifier="9448",
                                payment_date=date_started,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                            )
                        elif key == CardPaymentIncoming:
                            tx = CardPaymentIncoming(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_to=self.account_number,
                                year=self.year,
                                amount=amount,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                            )
                        elif key == BankPayedService:
                            tx = BankPayedService(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_from=self.account_number,
                                year=self.year,
                                amount=amount,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                                service_type="",
                            )
                        elif key == CardAtmCashOut:
                            tx = CardAtmCashOut(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_from=self.account_number,
                                year=self.year,
                                amount=amount,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                            )

                        self.all_transactions.append(tx)
                        if fee > 0:
                            tx_fee = BankPayedService(
                                statement_account=self.account_number,
                                parent_statement=self.file_path,
                                account_from=self.account_number,
                                year=self.year,
                                amount=fee * -1,
                                date_booked=date_completed,
                                currency=currency,
                                all_transaction_lines_text=description,
                                service_type="transaction fee",
                            )
                            self.all_transactions.append(tx_fee)

    @staticmethod
    def is_transaction_valid(state: str) -> bool:
        """Check if Revolut transaction has status "Completed" → is booked.

        Args:
            state (str): State of Revolut transaction. Can be either "Completed" or "Reverted".

        Returns:
            bool: True if transaction is valid and should be included in StatementAccount.
        """
        return state.lower() == "completed"
