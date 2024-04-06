"""This module provides functionality to create custom user rules to determine transaction details for
future analysis."""

from dataclasses import dataclass
from typing import List, Literal, Union

from src.transactions import Transaction


@dataclass
class TransactionRule:
    """Class representing custom user rules for analyzing transactions."""

    conditions_and: List["RuleCondition"]
    """conditions_and (List[RuleCondition]): List of conditions, that all have to passed by some transaction to pass
    this rule."""
    conditions_or: List["RuleCondition"]
    """conditions_or (List[RuleCondition]): List of conditions, from which at least 1 needs to be passed for transaction
    to pass this rule."""
    transaction_about: str
    """transaction_about (str): If transaction passes this rule, this value gets added to transaction info."""
    transaction_category: str
    """transaction_category (str): If transaction passes this rule, this value gets added to transaction info."""

    def is_transaction_passes(self, transaction: Transaction) -> bool:
        """Check if given Transaction instance passes this rule.

        Transaction must pass all conditions in conditions_and and at least 1 condition in conditions_or:

        Args:
            transaction (Transaction): _description_

        Returns:
            bool: _description_
        """
        # In case there are no condition - this should not happen.
        if not self.conditions_and and not self.conditions_or:
            return False

        condition_and_passed = all(condition.check_condition_passes(transaction) for condition in self.conditions_and)
        if not condition_and_passed:
            return False

        # If any conditions in OR conditions -> at least one of them must pass.
        if self.conditions_or:
            condition_or_passed = any(condition.check_condition_passes(transaction) for condition in self.conditions_or)
            return condition_or_passed

        return True


@dataclass
class RuleCondition:
    """Class representing custom rules for transactions."""

    check_tx_attribute: Literal[
        "type",
        "transaction_id",
        "statement_account",
        "account_from",
        "amount",
        "date_booked",
        "account_to",
        "currency",
        "account_from_name",
        "sender_note",
        "variable_symbol",
        "constant_symbol",
        "specific_symbol",
        "all_transaction_lines_text",
        "transaction_user_description",
        "transaction_user_category",
        "card_owner",
        "vendor_text",
    ]
    """check_tx_attribute (str): What attribute of transaction this rule checks. Must be one of Transaction class
    instance attributes"""
    comparison: Literal["less", "greater", "equal", "not equal", "is in", "not in"]  # Hint for allowed values.
    """comparison (str): What type of comparison check should be performed for this rule."""
    value: Union[bool, str, int, float]  # Type hint for value.
    """value Union[bool, str, int, float]: Value checked for this condition."""

    def __post_init__(self):
        """Post init method used to check valid instance arguments were passed to insatnce."""

        allowed_comparisons = {"less", "greater", "equal", "not equal", "is in", "not in"}
        if self.comparison not in allowed_comparisons:
            raise ValueError(f"Invalid comparison: {self.comparison}! Allowed comparisons are: {allowed_comparisons}")
        if not isinstance(self.value, (bool, str, int, float)):
            raise ValueError("Invalid value for condition provided. Value must be of type bool, str, int or float!")

    def check_condition_passes(self, transaction: Transaction) -> bool:
        """Check Transaction instance against this condition.

        Args:
            transaction (Transaction): Transaction instance to be checked.

        Returns:
            bool: Returns True if checked Transaction has relevant attribute with required value. False otherwise.
        """
        # First check transaction type if applicable
        if self.check_tx_attribute == "type":
            transaction_type = type(transaction).__name__
            if self.comparison == "equal" and transaction_type == self.value:
                return True
            elif self.comparison == "not equal" and transaction_type != self.value:
                return True
            else:
                return False

        # Else check other transaction attributes
        attribute_to_check = self.check_tx_attribute
        if hasattr(transaction, attribute_to_check):
            transaction_value = getattr(transaction, attribute_to_check)
            return self.validate(transaction_value)
        return False

    def validate(self, transaction_value: Union[str, int, float, List[str]]) -> bool:
        """Validate condition against given transaction attribute value

        Args:
            transaction_value (Union[str, int, float, List[str]]]): Value from transaction to be validated against this
                condition.

        Returns:
            bool: Returns True if transaction value passed this condition. Else otherwise.
        """
        if self.comparison == "less":
            return transaction_value < self.value
        elif self.comparison == "greater":
            return transaction_value > self.value
        elif self.comparison == "equal":
            return transaction_value == self.value
        elif self.comparison == "not equal":
            return transaction_value != self.value
        elif self.comparison == "is in":
            return self.value.lower() in transaction_value.lower()
        elif self.comparison == "not in":
            return self.value not in transaction_value
