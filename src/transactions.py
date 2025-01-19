"""This module implements functionality for account transactions."""

import json
import csv
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import ClassVar, List, Generator

from src.helper_functions import pdf_amount_to_float, get_amount_line
from src.helper_functions import text_contains_date, get_account_nr_line


@dataclass
class Transaction:
    """Data structure representing generic transaction."""

    all: ClassVar[List["Transaction"]] = []
    """Class attribute to hold all created instances of all transactions."""
    generator_id: ClassVar[Generator] = field(default=None)
    """Class attribute to hold Generator object producing new id for each new Transaction instance ."""
    # last_id: ClassVar[int] = 0

    statement_account: str
    """statement_account (str): Number of bank account, transaction was extracted from."""
    parent_statement: str = field(default=None)
    """parent_statement (str): Filepath of file, from which this transaction was created."""
    transaction_id: int = field(default=None, init=False)
    """transaction_id (int): Unique for each transaction."""
    year: int = field(default=None)
    """Year of given transaction."""
    account_from: str = field(default=None)
    """account_from (str): Account nr, from which received.
    Optional, Defaults to None."""
    amount: float = field(default=0)
    """amount (int): Amount received. Optional, Defaults to 0"""
    date_booked: str = field(default=None)
    """date_booked (str): Date, when transaction was booked to account
    in format:dd.mm.yyyy. Optional, Defaults to None."""
    account_to: str = field(default=None)
    """account_to (str): Account nr, to which sent.
    Optional, Defaults to None."""
    currency: str = field(default="CZK")
    """currency (str): Transaction currency.
    Optional. Defaults to CZK"""
    account_from_name: str = field(default=None)
    """account_from_name (str): Name on account, from which received.
    Optional, Defaults to None."""
    sender_note: str = field(default=None)
    """sender_note (str): Name on account, from which received.
    Optional, Defaults to None."""
    variable_symbol: int = field(default=None)
    """variable_symbol (int): Variable symbol for given transaction.
    Defaults to None."""
    constant_symbol: int = field(default=None)
    """constant_symbol (int): Constant symbol for given transaction.
    Defaults to None."""
    specific_symbol: int = field(default=None)
    """specific_symbol (int): Specific symbol for given transaction.
    Defaults to None."""
    all_transaction_lines_text: str = field(default_factory=str)
    """all_transaction_lines_text (str): All the text lines of this transaction from account statement combined
    together. Defaults to empty list."""
    user_description: str = field(default="")
    """transaction_description (str): User description of transaction.
    Optional, Defaults to None."""
    user_category: str = field(default="")
    """transaction_user_category (str): User defined category of transaction.
    Optional, Defaults to None."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        if Transaction.generator_id is None:
            Transaction.generator_id = Transaction.id_generator(start_id=1)
        self.transaction_id = next(Transaction.generator_id)
        Transaction.all.append(self)

    def get_transaction_description_and_category(self, rules: List) -> None:
        """Get transaction description and category based on transaction rules."""
        for rule in rules:
            if rule.is_transaction_passes(self):
                self.user_description += rule.transaction_about
                self.user_category += rule.transaction_category
                break
        return

    def __str__(self) -> str:
        return (
            f"Transakce\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}\n"
        )

    @classmethod
    def id_generator(cls, start_id: int = 0) -> Generator[int, None, None]:
        """Create generator for id generation.
        Args:
            start_id (int, optional): Starting id to generate next ids from.
            Defaults to 0.
        Yields:
            int: Next id. Initial = start_id.
        """
        idd = start_id
        while True:
            yield idd
            idd += 1

    @classmethod
    def save_transactions_json(cls) -> None:
        """Save all transactions into JSON file.

        Take all the transaction instances and, convert them into dictionary
        structure. Sort transactions by date and id. Save the result structure
        into JSON file.
        """
        cls.sort_transactions()
        # Reassign the id to match date order.
        for i, transaction in enumerate(cls.all):
            transaction.transaction_id = i + 1
        with open(r"transactions.json", "w", encoding="UTF-8") as file:
            transactions_data = [{"type": type(t).__name__, **asdict(t)} for t in cls.all]
            json.dump(transactions_data, file, indent=4, ensure_ascii=False)

    @classmethod
    def load_transactions_json(cls) -> None:
        """Load all transactions from JSON file.

        Load all historically already created transactions.
        Instantiate all of them.
        """
        try:
            with open(r"transactions.json", "r", encoding="UTF-8") as file:
                transactions_data = json.load(file)
                for transaction in transactions_data:
                    transaction_type = transaction.pop("type")
                    if transaction_type == "IncomingPayment":
                        IncomingPayment(**transaction)
                    elif transaction_type == "OutgoingPayment":
                        OutgoingPayment(**transaction)
                    elif transaction_type == "OutgoingPaymentPeriodic":
                        OutgoingPaymentPeriodic(**transaction)
                    elif transaction_type == "CardPaymentDebit":
                        CardPaymentDebit(**transaction)
                    elif transaction_type == "CardPaymentIncoming":
                        CardPaymentIncoming(**transaction)
                    elif transaction_type == "CardAtmCashOut":
                        CardAtmCashOut(**transaction)
                    elif transaction_type == "BankPayedService":
                        BankPayedService(**transaction)
                    elif transaction_type == "InterestPositive":
                        InterestPositive(**transaction)
                    elif transaction_type == "TaxInterest":
                        TaxInterest(**transaction)
                    elif transaction_type == "IncomingElectronicBankingTransfer":
                        ElectronicBankingTransfer(**transaction)
                    elif transaction_type == "DirectDebit":
                        DirectDebit(**transaction)
        except FileNotFoundError:
            pass

    @classmethod
    def sort_transactions(cls) -> None:
        """Sort all transactions.

        Sort by date from oldest and secondary by id from lowest.
        """

        def get_sort_key(tx) -> tuple[datetime, int]:
            """Generate sort key for each transaction in all list.

            Args:
                tx (Transaction): Transaction instance from Transaction
                    all list.

            Returns:
                tuple[datetime, int]: Tuple containing date booked of given
                    transaction and that transaction id.
            """
            return datetime.strptime(tx.date_booked, "%d.%m.%Y"), tx.transaction_id

        cls.all.sort(key=get_sort_key)

    @classmethod
    def transactions_to_csv(cls) -> None:
        with open(r"transactions.csv", "w", newline="", encoding="UTF-8-sig") as file:
            writer = csv.writer(file, delimiter=";")

            # Define your column headings
            headers = [
                "Transaction ID",
                "Transaction account",
                "Date Booked",
                "Type",
                "Account From",
                "Account To",
                "Amount",
                "Currency",
                "Category",
                "Description",
                "Transaction  data",
            ]
            # Write the column headings
            writer.writerow(headers)

            for tx in Transaction.all:
                service_type_clean = tx.service_type.replace("\n", "") if isinstance(tx, BankPayedService) else ""
                tx_type = f" - {service_type_clean}" if service_type_clean else ""
                writer.writerow(
                    [
                        tx.transaction_id,
                        tx.statement_account,
                        datetime.strptime(tx.date_booked, "%d.%m.%Y"),
                        tx.__class__.__name__ + tx_type,
                        tx.account_from,
                        tx.account_to,
                        str(tx.amount).replace(".", ","),
                        tx.currency,
                        tx.user_category,
                        tx.user_description,
                        tx.all_transaction_lines_text,
                    ]
                )


@dataclass
class IncomingPayment(Transaction):
    """Data structure representing incoming payments."""

    text_identifiers: ClassVar[dict] = {
        "cs": ["Příchozí úhrada", "Zahraniční příchozí úhrada"],
        "csob": ["Příchozí úhrada"],
    }
    """Class attribute to identify incoming transaction section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of incoming payments."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        IncomingPayment.all.append(self)

    def __str__(self) -> str:
        return (
            f"Příchozí platba\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_to: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "IncomingPayment":
        """Create and return new instance of IncomingPayment.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_to (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with incoming payment
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            IncomingPayment: Instance representing specific incoming payment.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            account_from = extracted_text_lines[line_index + 1].strip()
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            return IncomingPayment(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            account_from, account_from_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = extracted_text_lines[line_index + account_from_index - 2]
            amount = pdf_amount_to_float(amount_line.strip())
            return IncomingPayment(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )


@dataclass
class OutgoingPayment(Transaction):
    """Data structure representing outgoing payments."""

    text_identifiers: ClassVar[dict] = {"csob": ["Odchozí úhrada"], "cs": ["Tuzemská odchozí úhrada"]}
    """Class attribute to identify outgoing payments section
        in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of outgoing payments."""

    def __post_init__(self):
        """Post initialize method to track each created instace."""
        super().__post_init__()
        OutgoingPayment.all.append(self)

    def __str__(self) -> str:
        return (
            f"Odchozí úhrada\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "OutgoingPayment":
        """Create and return new instance of OutgoingPayment.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with outgoing payment
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            OutgoingPayment: Instance representing specific
                outgoing payment transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()
            if "okamžitá" in extracted_text_lines[line_index + 1]:
                offset = 1
            else:
                offset = 0
            account_to = extracted_text_lines[line_index + 1 + offset].strip()
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            return OutgoingPayment(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year
            account_to, account_to_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = extracted_text_lines[line_index + account_to_index - 2]
            amount = pdf_amount_to_float(amount_line.strip())
            return OutgoingPayment(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )


@dataclass
class OutgoingPaymentPeriodic(OutgoingPayment):
    """Data structure representing periodic outgoing payments."""

    text_identifiers: ClassVar[dict] = {"cs": ["Trvalý příkaz"], "csob": ["Trvalý příkaz"]}
    """Class attribute to identify periodic outgoing payments section
        in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of periodic outgoing payments."""

    def __post_init__(self):
        """Post initialize method to track each created instace."""
        super().__post_init__()
        OutgoingPaymentPeriodic.all.append(self)

    def __str__(self) -> str:
        return (
            f"Trvalý příkaz\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "OutgoingPaymentPeriodic":
        """Create and return new instance of OutgoingPaymentPeriodic.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with periodic outgoing payment
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            OutgoingPaymentPeriodic: Instance representing specific
                periodic outgoing payment transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()
            account_to, account_to_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            return OutgoingPaymentPeriodic(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year
            account_to, account_to_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = extracted_text_lines[line_index + account_to_index - 2]
            amount = pdf_amount_to_float(amount_line.strip())
            return OutgoingPaymentPeriodic(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )


@dataclass
class CardPaymentDebit(OutgoingPayment):
    """Data structure representing debit card payments."""

    text_identifiers: ClassVar[dict] = {"csob": ["Transakce platební kartou"], "cs": ["Platba kartou"]}
    """Class attribute to identify debit card payments section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of debit card payments."""

    payment_date: str = field(default=None)
    """payment_date (str): Date, when card payment occurred
        in format:dd.mm.yyyy. Does not have to be same as date booked.
        Defaults to None."""
    card_identifier: str = field(default=None)
    """card_identifier (str): Last 4 digits of used card card number.
        Defaults to None."""
    vendor_text: str = field(default=None)
    """vendor_text (str): Text input from vendor regarding payment.
        Defaults to None."""
    card_owner: str = field(default=None)
    """card_owner (str): Name of card owner. Should be Ondra or Mája.
        Defaults to None."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        self.card_owner = self.get_card_owner()
        super().__post_init__()
        CardPaymentDebit.all.append(self)

    def __str__(self) -> str:
        return (
            f"Platba kartou\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"karta:            {self.card_owner} - *{self.card_identifier}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"datum platby:     {self.payment_date}\n"
            f"text obchodníka:  {self.vendor_text}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    def get_card_owner(self) -> str:
        """Return name of the owner of given card based on its identifier.

        Returns:
            str: Name of the card owner.
        """
        card_owners = {
            "7148": "Ondra, ČS, VISA",
            "5567": "Ondra, ČSOB, MC",
            "1563": "Ondra, ČSOB, MC",
            "9448": "Ondra, REVOLUT, MC",
            "0119": "Mája, ČS, VISA",
        }
        return card_owners.get(self.card_identifier, "Unknown card")

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "CardPaymentDebit":
        """Create and return new instance of CardPaymentDebit.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with debit card
                payment transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            CardPaymentDebit: Instance representing specific
                debit card payment.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            variable_symbol = int(extracted_text_lines[line_index + 1].strip())
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            constant_symbol = int(extracted_text_lines[line_index + 3].strip())
            specific_symbol = int(extracted_text_lines[line_index + 4].strip())
            card_identifier = extracted_text_lines[line_index + 5].strip().split(" ")[0].replace("X", "")
            payment_date = extracted_text_lines[line_index + 5].strip().split(" ")[-1].replace("d.tran.", "")
            vendor_text = extracted_text_lines[line_index + 6].strip()

            return CardPaymentDebit(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                payment_date=payment_date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                specific_symbol=specific_symbol,
                card_identifier=card_identifier,
                vendor_text=vendor_text,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            amount_line, _ = get_amount_line(extracted_text_lines, line_index)
            amount = pdf_amount_to_float(amount_line.strip())

            variable_symbol = int(extracted_text_lines[line_index + 4].strip())
            constant_symbol = int(extracted_text_lines[line_index + 5].strip())
            specific_symbol = int(extracted_text_lines[line_index + 6].strip())
            card_identifier = extracted_text_lines[line_index + 6].strip()[-4:]
            payment_date = extracted_text_lines[line_index + 8].strip().split(" ")[-1]
            vendor_text = extracted_text_lines[line_index + 7].strip()
            vendor_text += extracted_text_lines[line_index + 9].strip()

            return CardPaymentDebit(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                payment_date=payment_date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                specific_symbol=specific_symbol,
                card_identifier=card_identifier,
                vendor_text=vendor_text,
            )


@dataclass
class CardPaymentIncoming(CardPaymentDebit):
    """Data structure representing incoming card payments."""

    text_identifiers: ClassVar[dict] = {"csob": ["Příchozí úhrada kartou"], "cs": ["Vratka platby kartou"]}
    """Class attribute to identify incoming card payments section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of incoming card payments."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        self.card_owner = self.get_card_owner()
        super().__post_init__()
        CardPaymentIncoming.all.append(self)

    def __str__(self) -> str:
        return (
            f"Příchozí úhrada kartou\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"karta:            {self.card_owner} - *{self.card_identifier}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"na účet:          {self.account_to}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"datum platby:     {self.payment_date}\n"
            f"text obchodníka:  {self.vendor_text}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_to: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "CardPaymentIncoming":
        """Create and return new instance of CardPaymentIncoming.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_to (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with debit card
                payment transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            CardPaymentIncoming: Instance representing specific
                incoming card payment.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()
            variable_symbol = int(extracted_text_lines[line_index + 1].strip())
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            constant_symbol = int(extracted_text_lines[line_index + 4].strip())
            specific_symbol = int(extracted_text_lines[line_index + 5].strip())
            card_identifier = extracted_text_lines[line_index + 6].strip().split(" ")[0].replace("X", "")
            payment_date = extracted_text_lines[line_index + 6].strip().split(" ")[-1].replace("d.tran.", "")
            vendor_text = extracted_text_lines[line_index + 7].strip()

            return CardPaymentDebit(
                statement_account=statement_account,
                year=year,
                amount=amount,
                date_booked=date,
                payment_date=payment_date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                specific_symbol=specific_symbol,
                card_identifier=card_identifier,
                vendor_text=vendor_text,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            amount_line = extracted_text_lines[line_index + 2]
            amount = pdf_amount_to_float(amount_line.strip())

            variable_symbol = int(extracted_text_lines[line_index + 4].strip())
            constant_symbol = int(extracted_text_lines[line_index + 5].strip())
            specific_symbol = int(extracted_text_lines[line_index + 6].strip())
            card_identifier = extracted_text_lines[line_index + 6].strip()[-4:]
            payment_date = extracted_text_lines[line_index + 8].strip().split(" ")[-1]
            vendor_text = extracted_text_lines[line_index + 7].strip()
            vendor_text += extracted_text_lines[line_index + 9].strip()

            return CardPaymentIncoming(
                statement_account=statement_account,
                year=year,
                account_to=account_to,
                amount=amount,
                date_booked=date,
                payment_date=payment_date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                specific_symbol=specific_symbol,
                card_identifier=card_identifier,
                vendor_text=vendor_text,
            )


@dataclass
class CardAtmCashOut(CardPaymentDebit):
    """Data structure representing ATM cash out."""

    text_identifiers: ClassVar[dict] = {"cs": ["Výběr hotovosti z bankomatu"], "csob": ["PLACEHOLDER"]}
    """Class attribute to identify ATM cash out section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of ATM cash out."""

    our_bank_atm: bool = field(default=True)
    """our_bank_atm (bool): True if cashed out from own bank ATM.
        False otherwise."""
    cash_out_date: str = field(default="")
    """cash_out_date (str): Date, when atm cash out occurred
        in format:dd.mm.yyyy. Does not have to be same as date booked.
        Defaults to None."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        self.card_owner = self.get_card_owner()
        super().__post_init__()
        CardAtmCashOut.all.append(self)

    def __str__(self) -> str:
        return (
            f"Výběr hotovosti z bankomatu - {'naše banka' if self.our_bank_atm else 'CIZÍ banka'}\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"karta:            {self.card_owner} - *{self.card_identifier}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"datum výběru:     {self.cash_out_date}\n"
            f"text obchodníka:  {self.vendor_text}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def is_our_bank_atm(line_index: int, extracted_text_lines: list[str]) -> bool:
        """Return False, if cash out was from other bank statement.
            Return True otherwise.

        Args:
            line_index (int): Index of line with ATM cash out transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            bool: False, if cash out from other bank statement. True otherwise.
        """
        other_bank_identifier_text = "jiné banky v ČR"
        is_our_bank = True
        if other_bank_identifier_text in extracted_text_lines[line_index + 1]:
            return False
        return is_our_bank

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "CardAtmCashOut":
        """Create and return new instance of CardAtmCashOut.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with ATM cash out transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            CardAtmCashOut: Instance representing specific
                ATM cash out transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            own_bank_atm = CardAtmCashOut.is_our_bank_atm(line_index, extracted_text_lines)
            if not own_bank_atm:
                offset = 1
            else:
                offset = 0
            variable_symbol = int(extracted_text_lines[line_index + 1 + offset].strip())
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            constant_symbol = int(extracted_text_lines[line_index + 3 + offset].strip())
            specific_symbol = int(extracted_text_lines[line_index + 4 + offset].strip())
            card_identifier = extracted_text_lines[line_index + 5 + offset].strip().split(" ")[0].replace("X", "")
            cash_out_date = extracted_text_lines[line_index + 5 + offset].strip().split(" ")[-1].replace("d.tran.", "")
            vendor_text = extracted_text_lines[line_index + 6 + offset].strip()

            return CardAtmCashOut(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                specific_symbol=specific_symbol,
                card_identifier=card_identifier,
                vendor_text=vendor_text,
                our_bank_atm=own_bank_atm,
                cash_out_date=cash_out_date,
            )


@dataclass
class CardAtmDeposit(IncomingPayment):
    """Data structure representing ATM cash deposit."""

    text_identifiers: ClassVar[dict] = {"cs": ["Vklad hotovosti přes bankomat"], "csob": ["PLACEHOLDER"]}
    """Class attribute to identify ATM cash deposit section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of ATM cash deposit."""

    deposit_date: str = field(default="")
    """deposit_date (str): Date, when atm cash depsit occurred
        in format:dd.mm.yyyy. Does not have to be same as date booked.
        Defaults to None."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        CardAtmDeposit.all.append(self)

    def __str__(self) -> str:
        return (
            f"Vklad hotovosti do bankomatu\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"datum vkladu:     {self.deposit_date}\n"
            f"text obchodníka:  {self.vendor_text}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "CardAtmDeposit":
        """Create and return new instance of CardAtmDeposit.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with ATM cash out transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            CardAtmDeposit: Instance representing specific
                ATM cash deposit transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            print(f"date: {date}")
            variable_symbol = int(extracted_text_lines[line_index + 1].strip())
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            constant_symbol = int(extracted_text_lines[line_index + 3].strip())
            deposit_date = date

            return CardAtmDeposit(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                account_to=statement_account,
                amount=amount,
                date_booked=date,
                variable_symbol=variable_symbol,
                constant_symbol=constant_symbol,
                deposit_date=deposit_date,
            )


@dataclass
class BankPayedService(Transaction):
    """Data structure representing various payed bank services."""

    text_identifiers: ClassVar[dict] = {"cs": ["Ceny za služby"], "csob": ["Poplatek-platební karta"]}
    """Class attribute to identify various payed bank services
        section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of various
        payed bank services."""

    service_type: str = field(default=None)
    """service_type (str): Type of bank payed service. There can be multiple
        types. Defaults to None."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        BankPayedService.all.append(self)

    def __str__(self) -> str:
        return (
            "Ceny za služby\n"
            f"{self.service_type}\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def get_cs_bank_service_type(line_index: int, extracted_text_lines: list[str]) -> str:
        """Get and return type of bank service. This information should be on
        the line after the bank service text line.

        Args:
            line_index (int): Index of line with bank payed services
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            str: Type of payed bank service.
        """
        cs_service_types = {
            "Cena za výběr hotovosti z bankomatu": [
                "jiné banky v ČR",
            ],
            "Cena za vedení účtu": [],
            "Poplatek": ["platební karta"],
        }
        service_type = ""
        for key, value in cs_service_types.items():
            if key in extracted_text_lines[line_index + 1]:
                service_type += key
                for subtype in value:
                    if subtype in extracted_text_lines[line_index + 2]:
                        service_type += f" - {subtype}"
                        break
                return service_type
        return service_type

    @staticmethod
    def get_csob_bank_service_type(line_index: int, extracted_text_lines: list[str]) -> str:
        """Get and return type of bank service. This information should be on
        the same line as service text line.

        Args:
            line_index (int): Index of line with bank payed services
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            str: Type of payed bank service.
        """
        csob_service_types = {
            "Poplatek": ["platební karta"],
        }
        service_type = "\n"
        for key, value in csob_service_types.items():
            if key in extracted_text_lines[line_index]:
                service_type += key
                for subtype in value:
                    if subtype in extracted_text_lines[line_index]:
                        service_type += f" - {subtype}"
                        break
                return service_type + "\n"
        return service_type

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "BankPayedService":
        """Create and return new instance of BankPayedService.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with various payed bank service
                transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            BankPayedService: Instance representing specific
                various payed bank service.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            service_type = BankPayedService.get_cs_bank_service_type(line_index, extracted_text_lines)

            return BankPayedService(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                service_type=service_type,
            )

        if bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())
            service_type = BankPayedService.get_csob_bank_service_type(line_index, extracted_text_lines)

            return BankPayedService(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                service_type=service_type,
            )


@dataclass
class InterestPositive(IncomingPayment):
    """Data structure representing incoming positive interest payments."""

    text_identifiers: ClassVar[dict] = {"cs": ["Kreditní úrok"], "csob": ["Zúčtování kladných úroků"]}
    """Class attribute to identify incoming positive interest transaction
    section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of incoming positive
    interest payments."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        InterestPositive.all.append(self)

    def __str__(self) -> str:
        return (
            f"Kreditní úrok\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "InterestPositive":
        """Create and return new instance of InterestPositive.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with incoming positive interest
                section text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            InterestPositive: Instance representing specific
                incoming positive interest section.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            account_to = account_from
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())

            return InterestPositive(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            account_to = account_from
            amount_line = extracted_text_lines[line_index + 2]
            amount = pdf_amount_to_float(amount_line.strip())

            return InterestPositive(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )


@dataclass
class TaxInterest(OutgoingPayment):
    """Data structure representing interest tax payment."""

    text_identifiers: ClassVar[dict] = {"cs": ["Daň z úroku"], "csob": ["PLACEHOLDER"]}
    """Class attribute to identify interest tax payment section
    in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of interest
    tax payments."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        TaxInterest.all.append(self)

    def __str__(self) -> str:
        return (
            f"Daň z úroku\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "TaxInterest":
        """Create and return new instance of TaxInterest.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with instances of interest
                tax payments transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            OutgoingPayment: Instance representing specific
                instances of interest tax payment transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())

            return TaxInterest(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
            )


@dataclass
class ElectronicBankingTransfer(IncomingPayment):
    """Data structure representing Electronic banking transfer."""

    text_identifiers: ClassVar[dict] = {"cs": ["PLACEHOLDER"], "csob": ["Bezhotovostní převod EB"]}
    """Class attribute to identify Electronic banking transfer
    section in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of Electronic
    banking transfer."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        ElectronicBankingTransfer.all.append(self)

    def __str__(self) -> str:
        return (
            f"Bezhotovostní převod EB\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "ElectronicBankingTransfer":
        """Create and return new instance of Electronic banking transfer.

        Can be both incomming and outgoing based on positive / negative amount
        transfered.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            line_index (int): Index of line with Electronic banking
                transfer text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            ElectronicBankingTransfer: Instance representing specific
                Electronic banking transfer.
        """
        if bank == "cs":
            pass

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            counter_party_account, counter_party_account_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = extracted_text_lines[line_index + counter_party_account_index - 2]
            amount = pdf_amount_to_float(amount_line.strip())
            # If negative amount → outgoing transaction
            if amount < 0:
                account_from = statement_account
                account_to = counter_party_account
            else:
                account_from = counter_party_account
                account_to = statement_account

            return ElectronicBankingTransfer(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )


@dataclass
class DirectDebit(OutgoingPayment):
    """Data structure representing direct debit transaction."""

    text_identifiers: ClassVar[dict] = {"cs": ["Inkaso"], "csob": ["Inkaso"]}
    """Class attribute to identify direct debit transaction section
    in text."""
    all: ClassVar[List] = []
    """Class attribute to hold all created instances of direct debit
    transactions."""

    def __post_init__(self):
        """Post initialize method to track each created instance."""
        super().__post_init__()
        DirectDebit.all.append(self)

    def __str__(self) -> str:
        return (
            f"Inkaso\n"
            "\n"
            f"ID tx:            {self.transaction_id}\n"
            f"účet transakce:   {self.statement_account}\n"
            f"na účet:          {self.account_to}\n"
            f"datum zaúčtování: {self.date_booked}\n"
            f"z účtu:           {self.account_from}\n"
            f"částka:           {self.amount} {self.currency}\n"
            f"popis:            {self.all_transaction_lines_text}"
        )

    @staticmethod
    def create(
        bank: str,
        year: int,
        statement_account: str,
        account_from: str,
        line_index: int,
        extracted_text_lines: list[str],
    ) -> "DirectDebit":
        """Create and return new instance of DirectDebit.

        Args:
            bank (str): Name of the bank.
            year (int): Year of the transaction.
            statement_account (str): Number of bank account, transaction was
                extracted from.
            account_from (str): Account number associated with given
                pdf statement.
            line_index (int): Index of line with direct debit transaction text.
            extracted_text_lines (list[str]): All the text lines from
                extracted pdf account statement.

        Returns:
            DirectDebit: Instance representing specific
                direct debit transaction.
        """
        if bank == "cs":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip()

            account_to, account_to_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = get_amount_line(extracted_text_lines, line_index)[0]
            amount = pdf_amount_to_float(amount_line.strip())

            return DirectDebit(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )

        elif bank == "csob":
            date = text_contains_date(extracted_text_lines[line_index])
            if not date:
                date = extracted_text_lines[line_index - 1].strip() + year

            account_to, account_to_index = get_account_nr_line(extracted_text_lines, line_index)
            amount_line = extracted_text_lines[line_index + account_to_index - 2]
            amount = pdf_amount_to_float(amount_line.strip())

            return DirectDebit(
                statement_account=statement_account,
                year=year,
                account_from=account_from,
                amount=amount,
                date_booked=date,
                account_to=account_to,
            )
