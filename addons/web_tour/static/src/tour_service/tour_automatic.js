import { tourState } from "./tour_state";
import { config as transitionConfig } from "@web/core/transition";
import { TourStepAutomatic } from "./tour_step_automatic";
import { browser } from "@web/core/browser/browser";
import { Mutex } from "@web/core/utils/concurrency";
import { setupEventActions } from "@web/../lib/hoot-dom/helpers/events";
import { MacroMutationObserver } from "@web/core/macro";

const mutex = new Mutex();

export class TourAutomatic {
    isComplete = false;
    mode = "auto";
    timer = null;
    previousStepIsJustACheck = false;
    constructor(data) {
        Object.assign(this, data);
        this.steps = this.steps.map((step, index) => new TourStepAutomatic(step, this, index));
        this.domStableDelay = this.checkDelay || 500;
        this.observer = new MacroMutationObserver(() => this.continue("mutation"));
        this.stepDelay = tourState.getCurrentConfig().stepDelay || 0;
        this.hasStarted = new Array(this.steps.length).fill(false);
        this.timeouts = new Array(this.steps.length).fill(false);
        this.stepElFound = new Array(this.steps.length).fill(false);
    }

    /**
     * @returns {TourStepAutomatic}
     */
    get currentStep() {
        return this.steps[this.currentIndex];
    }

    get debugMode() {
        const debugMode = tourState.getCurrentConfig().debug;
        return debugMode !== false;
    }

    start(pointer, callback) {
        this.callback = callback;
        this.pointer = pointer;
        setupEventActions(document.createElement("div"));
        transitionConfig.disabled = true;
        this.currentIndex = tourState.getCurrentIndex();
        if (this.debugMode && this.currentIndex === 0) {
            // eslint-disable-next-line no-debugger
            debugger;
        }
        this.observer.observe(document.body);
        this.continue("next");
    }

    stop() {
        transitionConfig.disabled = false;
        this.observer.disconnect();
        if (tourState.getCurrentTourOnError()) {
            console.error("tour not succeeded");
        } else {
            this.callback();
        }
    }

    async findTrigger() {
        const stepEl = this.currentStep.findTrigger();
        if (stepEl) {
            this.previousStepIsJustACheck = stepEl !== true && !this.currentStep.hasAction;
            this.stepElFound[this.currentIndex] = stepEl;
            this.removeTimer();
            await this.checkForIndeterminisms();
            if (this.debugMode && stepEl !== true) {
                this.pointer.pointTo(stepEl, this);
            }
            await this.doAction(stepEl);
        }
    }

    async doAction(stepEl) {
        const actionResult = await this.currentStep.doAction(stepEl);
        await this.pause();
        this.increment();
        if (!actionResult) {
            // await new Promise((resolve) => requestAnimationFrame(resolve));
            if (this.stepDelay) {
                await new Promise((resolve) => browser.setTimeout(resolve, this.stepDelay));
            }
            this.continue("next");
        }
    }

    /**
     * Add step to a queue via a mutex
     * @param {"mutation"|"next"} from
     */
    continue(from = null) {
        if (this.isComplete) {
            return;
        }
        // From "next" can only be called as first element in queue per step.
        if (from === "next" && this.hasStarted[this.currentIndex]) {
            return;
        }
        let delay = this.domStableDelay;
        // Called once per step.
        if (!this.hasStarted[this.currentIndex]) {
            console.log(`Step ${this.currentIndex + 1} has started from ${from}`);
            this.log();
            this.break();
            this.setTimer();
            delay = 150;
            if (this.previousStepIsJustACheck) {
                delay = 0;
            }
            this.hasStarted[this.currentIndex] = from;
        }
        this.clearTimeout();

        // Each time continue() is called and trigger has not been found yet.
        if (!this.stepElFound[this.currentIndex]) {
            this.timeouts[this.currentIndex] = browser.setTimeout(() => {
                console.log(
                    `[${this.currentIndex + 1}] Start findTrigger from ${from} after ${delay}`
                );
                mutex.exec(() => this.findTrigger());
            }, delay);
        }
    }

    /**
     * Allow to add a debugger to the tour at the current step
     */
    break() {
        if (this.currentStep.break && this.debugMode) {
            // eslint-disable-next-line no-debugger
            debugger;
        }
    }

    clearTimeout() {
        if (this.timeouts[this.currentIndex]) {
            browser.clearTimeout(this.timeouts[this.currentIndex]);
            this.timeouts[this.currentIndex] = false;
        }
    }

    log() {
        console.groupCollapsed(this.currentStep.describeMe);
        if (this.debugMode) {
            console.log(this.currentStep.stringify);
        }
        console.groupEnd();
    }

    increment() {
        this.currentIndex++;
        if (this.currentIndex === this.steps.length) {
            this.isComplete = true;
            this.stop();
            return;
        }
        tourState.setCurrentIndex(this.currentIndex);
    }

    setTimer() {
        const timeout = this.currentStep.timeout || 10000;
        this.timer = browser.setTimeout(
            () =>
                this.currentStep.throwError(
                    `TIMEOUT: This step cannot be succeeded within ${timeout}ms.`
                ),
            timeout
        );
    }

    async checkForIndeterminisms() {
        const checkDelay = parseInt(tourState.getCurrentConfig().check);
        if (checkDelay > 0) {
            const duration = checkDelay * 1000;
            await new Promise((resolve) => {
                browser.setTimeout(() => {
                    const stepEl = this.currentStep.findTrigger();
                    if (this.stepElFound[this.currentIndex] === stepEl) {
                        resolve();
                    } else {
                        this.currentStep.throwError(
                            `UNDETERMINISTIC: two differents elements has been found in ${duration}ms`
                        );
                    }
                }, duration);
            });
        }
    }

    removeTimer() {
        this.clearTimeout();
        if (this.timer) {
            browser.clearTimeout(this.timer);
        }
    }

    /**
     * Allow to pause the tour at current step
     */
    async pause() {
        if (!this.isComplete && this.currentStep.pause && this.debugMode) {
            const styles = [
                "background: black; color: white; font-size: 14px",
                "background: black; color: orange; font-size: 14px",
            ];
            console.log(
                `%cTour is paused. Use %cplay()%c to continue.`,
                styles[0],
                styles[1],
                styles[0]
            );
            await new Promise((resolve) => {
                window.play = () => {
                    resolve();
                    delete window.play;
                };
            });
        }
    }
}
