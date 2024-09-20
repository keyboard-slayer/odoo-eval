import { _legacyIsVisible } from "@web/core/utils/ui";
import { tourState } from "./tour_state";
import * as hoot from "@odoo/hoot-dom";
import { callWithUnloadCheck } from "./tour_utils";
import { TourHelpers } from "./tour_helpers";
import { TourStep } from "./tour_step";

export class TourStepAutomatic extends TourStep {
    triggerFound = false;
    hasRun = false;
    isUIBlocked = true;
    running = false;
    element = null;
    constructor(data, tour, index) {
        super(data, tour);
        this.index = index;
        this.tourConfig = tourState.getCurrentConfig();
    }

    findTrigger() {
        if (!this.active) {
            this.run = null;
            return true;
        }

        let nodes;
        try {
            nodes = hoot.queryAll(this.trigger);
        } catch (error) {
            this.throwError(`HOOT: ${this.trigger} : ${error.message}`);
        }
        this.element = this.trigger.includes(":visible")
            ? nodes.at(0)
            : nodes.find(_legacyIsVisible);
        // If DOM is blocked by UI.
        this.isUIBlocked =
            document.body.classList.contains("o_ui_blocked") ||
            document.querySelector(".o_blockUI");
        if (this.isUIBlocked) {
            return false;
        } else {
            return this.element;
        }
    }

    async doAction(stepEl) {
        // TODO: Delegate the following routine to the `ACTION_HELPERS` in the macro module.
        const actionHelper = new TourHelpers(stepEl);

        let result;
        if (typeof this.run === "function") {
            const willUnload = await callWithUnloadCheck(async () => {
                await this.tryToDoAction(() =>
                    // `this.anchor` is expected in many `step.run`.
                    this.run.call({ anchor: stepEl }, actionHelper)
                );
            });
            result = willUnload && "will unload";
        } else if (typeof this.run === "string") {
            for (const todo of this.run.split("&&")) {
                const m = String(todo)
                    .trim()
                    .match(/^(?<action>\w*) *\(? *(?<arguments>.*?)\)?$/);
                await this.tryToDoAction(() => actionHelper[m.groups?.action](m.groups?.arguments));
            }
        }
        return result;
    }

    get describeWhyIFailed() {
        const errors = [];
        if (this.element) {
            errors.push(`Element has been found.`);
            if (this.isUIBlocked) {
                errors.push("ERROR: DOM is blocked by UI.");
            } else if (!this.hasRun) {
                errors.push("BUT: an error has triggered in run().");
            }
        } else {
            errors.push(`Element has not been found.`);
        }
        return errors;
    }

    get describeWhereIFailed() {
        const offset = 3;
        const start = Math.max(this.index - offset, 0);
        const end = Math.min(this.index + offset, this.tour.steps.length - 1);
        const result = [];
        for (let i = start; i <= end; i++) {
            const stepString = new TourStep(this.tour.steps[i]).stringify;
            const text = [stepString];
            if (i === this.index) {
                const line = "-".repeat(10);
                const failing_step = `${line} FAILED: ${this.describeMe} ${line}`;
                text.unshift(failing_step);
                text.push("-".repeat(failing_step.length));
            }
            result.push(...text);
        }
        return result.join("\n");
    }

    // Check is this step has a run
    get hasAction() {
        return ["string", "function"].includes(typeof this.run);
    }

    /**
     * @param {string} [error]
     */
    throwError(error = "") {
        tourState.setCurrentTourOnError();
        const tourConfig = tourState.getCurrentConfig();
        // console.error notifies the test runner that the tour failed.
        const errors = [`FAILED: ${this.describeMe}.`, error, ...this.describeWhyIFailed];
        console.error(errors.filter(Boolean).join("\n"));
        // The logged text shows the relative position of the failed step.
        // Useful for finding the failed step.
        console.dir(this.describeWhereIFailed);
        if (tourConfig.debug !== false) {
            // eslint-disable-next-line no-debugger
            debugger;
        }
    }

    async tryToDoAction(action) {
        try {
            await action();
            this.hasRun = true;
        } catch (error) {
            this.throwError(error.message);
        }
    }
}
