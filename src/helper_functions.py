"""This module holds helpers functions used within the application."""

from datetime import datetime
import json
import re


def get_account_bank(extracted_lines: list[str]) -> str:
    """Get name of bank of given account statement.
    Args:
        lines (list[str]): List of lines to search for bank name.
    Returns:
        str: Name of bank.
    """
    bank_names = {
        "Československá obchodní banka, a. s.,": "csob",
        "Česká spořitelna, a.s.,": "cs",
        "Revolut": "revolut",
    }
    bank_name = ""
    for line in extracted_lines:
        for key in bank_names:
            if key in line:
                return bank_names.get(key)
    return bank_name


def is_revolut_transaction_start(line: str, bank_name: str) -> bool:
    """Check, if line contains date only date. Such line identifies transaction
    section in Revolut account statements.

    Args:
        line (str): Text line from account statement.
        bank_name (str): Name of bank for which given statement is.

    Returns:
        bool: True if starting line of Revolut transaction. False otherwise.
    """
    # This pattern will match dates where the day and month are one or two
    # digits, and the year is exactly four digits, with optional spaces around the dots.
    tx_start_pattern = r"^\s*\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\s*$"
    if bank_name == "revolut" and re.match(tx_start_pattern, line):
        return True
    return False


def is_revolut_incoming_tx(extracted_lines: list[str], search_from_line_index: int) -> bool:
    # This pattern will match strings that represent monetary amounts
    # in the format of "X,XXX.XX CZK", where X is any digit, and it allows for any number of thousand separators.
    amount_pattern = r"^\d{1,3}(,\d{3})*\.\d{2}\sCZK$"
    # now search for 2 lines with amount data in them (amount change and final amount)
    count_found = 0
    change_line, change_line_index = None, None
    final_line, final_line_index = None, None

    for i, line in enumerate(extracted_lines[search_from_line_index:]):
        if count_found == 0:
            if re.match(amount_pattern, line):
                change_line, change_line_index = line, i
                count_found += 1
        elif count_found == 1:
            if re.match(amount_pattern, line):
                final_line, final_line_index = line, i
                count_found += 1
        else:
            break

    pass


def is_revolut_outgoing_tx(extracted_lines: list[str], search_from_line_index: int) -> bool:
    pass


def pdf_amount_to_float(amount_text: str) -> float:
    """Take amount string from pdf and return its float number representation.

    Args:
        amount_text (str): Text line with amount.
        Examples: "+30 000,00", "-30 000.00"
    Returns:
        float: Float number representation of input text.
    """
    return round(float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2)


def find_account_number(extracted_text_lines: list[str]) -> str:
    """Get the account number of given pdf statement."

    Args:
        extracted_text_lines (list[str]): Extracted text lines from pdf.
    Returns:
        str: Account number in string format.
    """
    account_number = ""
    for i, line in enumerate(extracted_text_lines):
        if "Číslo účtu/kód banky:" in line:  # CS rule.
            return line.replace("Číslo účtu/kód banky:", "").strip()
        elif line.strip() == "Účet:":  # CSOB rule.
            return extracted_text_lines[i + 1].strip()
        elif re.match(r"^LT\d*$", line.strip()) and "REVOLT21" in extracted_text_lines[i + 1]:  # Revolut rule.
            return line.strip()
    return account_number


def get_account_start_balance(extracted_text_lines: list[str], statement_bank: str) -> float:
    """Get the account balance at the start of given period."

    Args:
        extracted_text_lines (list[str]): Extracted text lines from pdf.
        statement_bank (str): Name of bank of given statement.
    Returns:
        float: Account start balance for given statement.
    """
    account_start_balance = None
    for i, line in enumerate(extracted_text_lines):
        if "Počáteční zůstatek:" in line and statement_bank in ["csob", "cs"]:  # CS + CSOB rule
            amount_text = extracted_text_lines[i + 1]
            account_start_balance = round(float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2)
        elif "Souhrn zůstatku" in line and statement_bank == "revolut":  # Revolut rule CZ
            for o, line in enumerate(extracted_text_lines[i:]):
                if line.strip() == "Celkem":
                    amount_text = extracted_text_lines[
                        i + o + 1
                    ]  # End balance should be 1st line after "Celkem:" line.
                    account_start_balance = round(float(amount_text.replace(" CZK", "").replace(",", "")), 2)
    return account_start_balance


def get_account_end_balance(extracted_text_lines: list[str], statement_bank: str) -> float:
    """Get the account balance at the end of given period."

    Args:
        extracted_text_lines (list[str]): Extracted text lines from pdf.
        statement_bank (str): Name of bank of given statement.
    Returns:
        float: Account end balance for given statement.
    """
    account_end_balance = None
    if statement_bank == "revolut":  # Revolut rule CZ
        # There can be multiple summary sections and each regarding only part of the month.
        # So we need to find the last summary section of all pages to get mont end balance.
        last_summary_section_index = None
        for i, line in enumerate(extracted_text_lines):
            if "Souhrn zůstatku" in line:
                last_summary_section_index = i
        for o, line in enumerate(extracted_text_lines[last_summary_section_index:]):
            if line.strip() == "Celkem":
                amount_text = extracted_text_lines[
                    last_summary_section_index + o + 4
                ]  # End balance should be 4th line after "Celkem:" line.
                account_end_balance = round(float(amount_text.replace(" CZK", "").replace(",", "")), 2)
    elif statement_bank in ["csob", "cs"]:
        for i, line in enumerate(extracted_text_lines):
            if "Konečný zůstatek:" in line:
                amount_text = extracted_text_lines[i + 1]
                account_end_balance = round(
                    float(amount_text.replace(" ", "").replace("\xa0", "").replace(",", ".")), 2
                )
    return account_end_balance


def get_amount_line(lines: list[str], search_from_line_index: int) -> tuple[str, int]:
    """Get line text and line index of line containing amount.
    Args:
        lines (list[str]): List of lines to search for amount line.
        search_from_line_index (int): Index of line to search amount
          line from.
    Returns:
        tuple[str, int]: Tuple containing the amount line text and that
          line index.
    """
    for i, line in enumerate(lines[search_from_line_index:]):
        if ("-" in line) or ("+" in line) or (line == "0.00"):
            potential_amount_line = (
                line.replace("+", "")
                .replace("-", "")
                .replace(" ", "")
                .replace("\xa0", "")
                .replace(".", "")
                .replace(",", "")
            )
            if potential_amount_line.isdigit():
                return line, i
    return None, None


def get_all_lines_before_amount(
    section_text_line_index: int, amount_line_index: int, extracted_lines: list[str]
) -> list[str]:
    """Get all the text lines between section identifier line and amount line.

    This can be any additional transaction info like VS, SS
    as well as senders note etc.

    Args:
        section_text_line_index (int): Section identifier line index in all
            extracted lines list.
        amount_line_index (int): Amount line index in all extracted lines list.
        extracted_lines (list[str]): All pdf extracted lines list.

    Returns:
        list[str]: Return text lines between section identifier
            line and amount line.
    """
    return [line for line in extracted_lines[section_text_line_index:amount_line_index]]


def get_statement_year(extracted_lines: list[str]) -> str:
    """Get year of pdf statement.

    Args:
        extracted_lines (list[str]): All tex lines from pdf statement.

    Returns:
        str: Year of statement.
    """
    for i, line in enumerate(extracted_lines):
        if line.strip() == "Období:":  # CS + CSOB rule
            return extracted_lines[i + 1].strip()[-4:]
        elif "Transakce účtu od" in line:  # Revolut rule
            return line.strip()[-4:]
    return ""


def text_contains_date(text: str) -> list:
    """Search for date pattern in string. Return list of matches.

    Args:
        text (str): Test to search for date in.

    Returns:
        list: List of matches, if any found, else None.
    """
    pattern = r"\b\d{2}\.\d{2}\.\d{4}\b"
    matches = re.findall(pattern, text)

    return matches[0] if matches else None


def get_date_from_string(date_string: str) -> str:
    """Transform Revolut format datetime string into date string in fotmat dd.mm.yyyy.

    Args:
        date_string (str): Original Revolut datetime string to be transformed.

    Returns:
        str: Date string in fotmat dd.mm.yyyy
    """
    revolut_format = "%Y-%m-%d %H:%M:%S"
    date_object = datetime.strptime(date_string, revolut_format)
    return date_object.strftime("%d.%m.%Y")


def get_account_nr_line(extracted_lines: list[str], search_from_line_index: int) -> tuple[str, int]:
    """Get line text and line index of line containing account number.
    Args:
        lines (list[str]): List of lines to search for account number line.
        search_from_line_index (int): Index of line to search account number
            line from.
    Returns:
        tuple[str, int]: Tuple containing the account number line text and that
            line index.
    """
    pattern = r"\d{4}/\d{4}"
    for i, line in enumerate(extracted_lines[search_from_line_index:]):
        if re.findall(pattern, line):
            return line.strip(), i
    return None, None


def save_settings(settings: dict, filename: str) -> None:
    """Save relevant scripts settings into JSON file.

    Args:
        settings (dict): Relevant settings dictionary.
        filename (str): Path, where to save the settings file.
    """
    with open(filename, "w", encoding="UTF-8") as file:
        json.dump(settings, file, indent=4)


def load_settings(filename: str) -> dict:
    """Load relevant scripts settings from JSON file. Return settings dict.

    Args:
        filename (str): Path, to the settings file.

    Returns:
        dict: Dictionary with relevant settings.
    """
    with open(filename, "r", encoding="UTF-8") as file:
        return json.load(file)
