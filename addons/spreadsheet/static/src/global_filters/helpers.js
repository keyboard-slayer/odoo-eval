/** @ts-check */

import { CommandResult } from "@spreadsheet/o_spreadsheet/cancelled_reason";
import {
    RELATIVE_DATE_RANGE_REFERENCES,
    RELATIVE_DATE_RANGE_UNITS,
} from "@spreadsheet/helpers/constants";

/**
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 */

/**
 * Check that the given value is compatible with the given type, and the rangeType
 * in case of a date filter.
 * @param {"text" | "date" | "relation"} type
 * @param {unknown} value
 * @param {[import("@spreadsheet").RangeType]} rangeType
 * @returns {CommandResult}
 */
export function checkFiltersTypeValueCombination(type, value, rangeType) {
    if (value !== undefined) {
        switch (type) {
            case "text":
                if (typeof value !== "string") {
                    return CommandResult.InvalidValueTypeCombination;
                }
                break;
            case "date": {
                if (rangeType === "relative") {
                    const expectedReferences = RELATIVE_DATE_RANGE_REFERENCES.map(
                        (ref) => ref.type
                    );
                    const expectedUnits = RELATIVE_DATE_RANGE_UNITS.map((unit) => unit.type);
                    if (
                        expectedReferences.includes(value.reference) &&
                        expectedUnits.includes(value.unit)
                    ) {
                        return CommandResult.Success;
                    }
                    return CommandResult.InvalidValueTypeCombination;
                }
                if (value === "") {
                    return CommandResult.Success;
                } else if (typeof value === "string") {
                    const expectedValues = ["this_month", "this_quarter", "this_year"];
                    if (expectedValues.includes(value)) {
                        return CommandResult.Success;
                    }
                    return CommandResult.InvalidValueTypeCombination;
                } else if (typeof value !== "object") {
                    return CommandResult.InvalidValueTypeCombination;
                }
                break;
            }
            case "relation":
                if (value === "current_user") {
                    return CommandResult.Success;
                }
                if (!Array.isArray(value)) {
                    return CommandResult.InvalidValueTypeCombination;
                }
                break;
        }
    }
    return CommandResult.Success;
}

/**
 *
 * @param {Record<string, FieldMatching>} fieldMatchings
 */
export function checkFilterFieldMatching(fieldMatchings) {
    for (const fieldMatch of Object.values(fieldMatchings)) {
        if (fieldMatch.offset && (!fieldMatch.chain || !fieldMatch.type)) {
            return CommandResult.InvalidFieldMatch;
        }
    }

    return CommandResult.Success;
}
