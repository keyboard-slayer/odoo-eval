/** @odoo-module */

import { TestRunner } from "../../core/runner";
import { Suite } from "../../core/suite";
import { describe, expect, test } from "../../hoot";
import { parseUrl } from "../local_helpers";

describe(parseUrl(import.meta.url), () => {
    test("can register suites", () => {
        const runner = new TestRunner();
        runner.describe("a suite", () => {});
        runner.describe("another suite", () => {});

        expect(runner.suites.length).toBe(2);
        expect(runner.tests.length).toBe(0);
        for (const suite of runner.suites) {
            expect(suite).toMatch(Suite);
        }
    });

    test("can register nested suites", () => {
        const runner = new TestRunner();
        runner.describe(["a", "b", "c"], () => {});

        expect(runner.suites.map((s) => s.name)).toEqual(["a", "b", "c"]);
    });

    test("can register tests", () => {
        const runner = new TestRunner();
        runner.describe("suite 1", () => {
            runner.test("test 1", () => {});
        });
        runner.describe("suite 2", () => {
            runner.test("test 2", () => {});
            runner.test("test 3", () => {});
        });

        expect(runner.suites.length).toBe(2);
        expect(runner.tests.length).toBe(3);
    });

    test("should not have duplicate suites", () => {
        const runner = new TestRunner();
        runner.describe(["parent", "child a"], () => {});
        runner.describe(["parent", "child b"], () => {});

        expect(runner.suites.map((suite) => suite.name)).toEqual(["parent", "child a", "child b"]);
    });

    test("can refuse standalone tests", async () => {
        const runner = new TestRunner();
        expect(() =>
            runner.test([], "standalone test", () => {
                expect(true).toBe(false);
            })
        ).toThrow();
    });

    test("can register test tags", async () => {
        const runner = new TestRunner();
        runner.describe("suite", () => {
            let testFn = runner.test.debug.only.skip;
            for (let i = 1; i <= 10; i++) {
                testFn = testFn.tags(`Tag ${i}`);
            }

            testFn("tagged test", () => {});
        });

        expect(runner.tags.size).toBe(10);
        expect(runner.tests[0].tags.length).toBe(10 + 3);
    });
});
