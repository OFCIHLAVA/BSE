import os
import argparse

from src.account_statement import StatementAccount
from src.transactions import Transaction
from src.transaction_rules import RULES


def get_files_to_process(folder_path: str, suffixes: list[str]) -> list[str]:
    """Search folder and all its sub-folders for files with any suffix specified in suffixes.

    Args:
        folder_path (str): Path to directory to search.
        suffixes (list[str]): list of file suffixes to search for.
    Returns:
        list[str]: List of full paths of all found files within that directory or its subdirectories.
    Note:
        Case insensitive.
    """
    files = []
    suffixes = [s.lower() for s in suffixes]
    for dirpath, _, filenames in os.walk(folder_path):
        if filenames:
            for f in filenames:
                if any(f.endswith(suffix.lower()) for suffix in suffixes):
                    file_path = os.path.join(dirpath, f)
                    files.append(file_path)
    return files


def load_pdfs(folder_path: str) -> None:
    """Create StatementAccount instance from each pdf file in some directory.

    Note:
        All theStatementAccount instances gets saved into the StatementAccount.all attribute.

    Args:
        folder_path (str): Full path to the root directory containing pdf files.
    """
    pdfs = get_files_to_process(folder_path, [".pdf"])
    for pdf in pdfs:
        StatementAccount(pdf)


def load_csvs(folder_path: str) -> None:
    """Create StatementAccount instance from each csv file in some directory.

    Note:
        All theStatementAccount instances gets saved into the StatementAccount.all attribute.

    Args:
        folder_path (str): Full path to the root directory containing pdf files.
    """
    csvs = get_files_to_process(folder_path, [".csv"])
    for csv in csvs:
        StatementAccount(csv)


def analyze_all_transactions(rules) -> None:
    """Checks all the transactions against the user defined set of rules to analyze them."""
    for tx in Transaction.all:
        tx.get_transaction_description_and_category(rules)


def validate_all_transactions_extracted():
    """Checks all the StatementAccount instances, if all the transactions from them have been extracted.

    Check consists of comparing sum of all the transaction amounts from given statement vs difference between
    statement end and start balance. If not equal, some transactions was not identified.
    """
    for s in StatementAccount.all:
        print(s.file_path)
        # print(len(s.all_transactions))
        # print(round(s.end_balance - s.start_balance, ndigits=2))
        # print(round(sum([t.amount for t in s.all_transactions]), ndigits=2))
        if (round(s.end_balance - s.start_balance, ndigits=2)) != (
            round(sum([t.amount for t in s.all_transactions]), ndigits=2)
        ):
            print(
                f"""WARNING!: There are some transaction, that not have been extracted!
            Sum amount of missing transactions = {round((s.end_balance - s.start_balance)-sum([t.amount for t in s.all_transactions]), ndigits=2)}"""
            )
        # for i, t in enumerate(s.all_transactions):
        #     print(i, t)
        #     input()


def save_transactions():
    """Save all the extracted transaction instances.

    Save to JSON and csv format.
    """
    Transaction.save_transactions_json()
    Transaction.transactions_to_csv()


def main(folder_path: str) -> None:

    load_pdfs(folder_path=folder_path)
    load_csvs(folder_path=folder_path)
    analyze_all_transactions(rules=RULES)
    validate_all_transactions_extracted()
    save_transactions()


if __name__ == "__main__":

    argparser = argparse.ArgumentParser(description="Bank statement extractor.")
    argparser.add_argument(
        "-i",
        "--input",
        required=True,
        dest="path",
        type=str,
        help="Provide full path to the directory with pdfs to process in format: '-i/-input <full_path_to_directory>'",
    )
    path = argparser.parse_args().path
    if not os.path.exists(path):
        print(
            f"\033[31mERROR\033[0m - Provided path to the pdfs directory: \033[35m{path}\033[0m does not exists, nothing to process. Exiting..."
        )
    main(path)
