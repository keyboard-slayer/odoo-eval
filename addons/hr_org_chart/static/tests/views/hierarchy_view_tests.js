/** @odoo-module **/

import { click, drag, dragAndDrop, getFixture, getNodesTextContent } from "@web/../tests/helpers/utils";
import { makeView, setupViewRegistries } from "@web/../tests/views/helpers";

let serverData, target;

QUnit.module("Views", (hooks) => {
    hooks.beforeEach(() => {
        serverData = {
            models: {
                "hr.employee": {
                    fields: {
                        parent_id: { string: "Manager", type: "many2one", relation: "hr.employee" },
                        name: { string: "Name" },
                        child_ids: { string: "Subordinates", type: "one2many", relation: "hr.employee", relation_field: "parent_id" },
                    },
                    records: [
                        { id: 1, name: "Albert", parent_id: false, child_ids: [2, 3] },
                        { id: 2, name: "Georges", parent_id: 1, child_ids: [] },
                        { id: 3, name: "Josephine", parent_id: 1, child_ids: [4] },
                        { id: 4, name: "Louis", parent_id: 3, child_ids: [] },
                    ],
                },
            },
            views: {
                "hr.employee,false,hierarchy": `
                    <hierarchy>
                        <templates>
                            <t t-name="hierarchy-box">
                                <div class="o_hierarchy_node_header">
                                    <field name="name"/>
                                </div>
                                <div class="o_hierarchy_node_body">
                                    <field name="parent_id"/>
                                </div>
                            </t>
                        </templates>
                    </hierarchy>
                `,
                "hr.employee,1,hierarchy": `
                    <hierarchy child_field="child_ids">
                        <field name="child_ids" invisible="1"/>
                        <templates>
                            <t t-name="hierarchy-box">
                                <div class="o_hierarchy_node_header">
                                    <field name="name"/>
                                </div>
                                <div class="o_hierarchy_node_body">
                                    <field name="parent_id"/>
                                </div>
                            </t>
                        </templates>
                    </hierarchy>
                `,
                "hr.employee,false,form": `
                    <form>
                        <sheet>
                            <group>
                                <field name="name"/>
                                <field name="parent_id"/>
                            </group>
                        </sheet>
                    </form>
                `,
            },
        };
        setupViewRegistries();
        target = getFixture();
    });

    QUnit.module("Hierarchy View");

    QUnit.test("load hierarchy view", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
        });

        assert.containsOnce(target, ".o_hierarchy_view");
        assert.containsN(target, ".o_hierarchy_button_add", 2);
        assert.containsOnce(target, ".o_hierarchy_view .o_hierarchy_renderer");
        assert.containsOnce(target, ".o_hierarchy_view .o_hierarchy_renderer > .o_hierarchy_container");
        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsOnce(target, ".o_hierarchy_separator");
        assert.containsN(target, ".o_hierarchy_line_part", 2);
        assert.containsOnce(target, ".o_hierarchy_line_left");
        assert.containsOnce(target, ".o_hierarchy_line_right");
        assert.containsN(target, ".o_hierarchy_node_container", 3);
        assert.containsN(target, ".o_hierarchy_node", 3);
        assert.containsNone(target, ".o_hierarchy_node_highlighted");
        assert.containsN(target, ".o_hierarchy_node_button", 2);
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-primary");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_button.btn-primary").textContent.trim(), "Unfold 1");
        // check nodes in each row
        const row = target.querySelector(".o_hierarchy_row");
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "Albert");
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-secondary");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_button.btn-secondary").textContent.trim(), "Fold");
    });

    QUnit.test("display child nodes", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            async mockRPC(route, args) {
                if (args.method === "read") {
                    assert.step("get child data");
                } else if (args.method === "read_group") {
                    assert.step("fetch descendants");
                }
            }
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node_button", 2);
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-secondary");
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-primary");
        await click(target,  ".o_hierarchy_node_button.btn-primary");
        assert.containsN(target, ".o_hierarchy_row", 3);
        assert.containsN(target, ".o_hierarchy_separator", 2);
        assert.containsN(target, ".o_hierarchy_line_part", 4);
        assert.containsN(target, ".o_hierarchy_line_left", 2);
        assert.containsN(target, ".o_hierarchy_line_right", 2);
        assert.containsN(target, ".o_hierarchy_node_container", 4);
        assert.containsN(target, ".o_hierarchy_node", 4);
        assert.containsN(target, ".o_hierarchy_node_button", 2);
        assert.containsNone(target, ".o_hierarchy_node_button.btn-primary");
        assert.containsN(target, ".o_hierarchy_node_button.btn-secondary", 2);
        assert.strictEqual(target.querySelector(".o_hierarchy_node_button.btn-secondary").textContent.trim(), "Fold");
        // check nodes in each row
        const rows = target.querySelectorAll(".o_hierarchy_row");
        let row = rows[0];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "Albert");
        row = rows[1];
        assert.containsN(row, ".o_hierarchy_node", 2);
        assert.deepEqual(
            getNodesTextContent(row.querySelectorAll(".o_hierarchy_node_content")),
            [ // Name + Parent name
                "GeorgesAlbert",
                "JosephineAlbert",
            ],
        );
        row = rows[2];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "LouisJosephine");
        assert.verifySteps([
            "get child data",
            "fetch descendants",
        ]);
    });

    QUnit.test("display child nodes with child_field set on the view", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            viewId: 1,
            async mockRPC(route, args) {
                if (args.method === "read") {
                    assert.step("get child data with descendants");
                }
            }
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node_button", 2);
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-secondary");
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-primary");
        await click(target,  ".o_hierarchy_node_button.btn-primary");
        assert.containsN(target, ".o_hierarchy_row", 3);
        assert.containsN(target, ".o_hierarchy_separator", 2);
        assert.containsN(target, ".o_hierarchy_line_part", 4);
        assert.containsN(target, ".o_hierarchy_line_left", 2);
        assert.containsN(target, ".o_hierarchy_line_right", 2);
        assert.containsN(target, ".o_hierarchy_node_container", 4);
        assert.containsN(target, ".o_hierarchy_node", 4);
        assert.containsN(target, ".o_hierarchy_node_button", 2);
        assert.containsNone(target, ".o_hierarchy_node_button.btn-primary");
        assert.containsN(target, ".o_hierarchy_node_button.btn-secondary", 2);
        assert.verifySteps([
            "get child data with descendants",
        ]);
    });

    QUnit.test("collapse child nodes", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsOnce(target, ".o_hierarchy_separator");
        assert.containsN(target, ".o_hierarchy_line_part", 2);
        assert.containsOnce(target, ".o_hierarchy_line_left");
        assert.containsOnce(target, ".o_hierarchy_line_right");
        assert.containsN(target, ".o_hierarchy_node_container", 3);
        assert.containsN(target, ".o_hierarchy_node", 3);
        await click(target, ".o_hierarchy_node_button.btn-secondary");
        assert.containsOnce(target, ".o_hierarchy_row");
        assert.containsNone(target, ".o_hierarchy_separator");
        assert.containsNone(target, ".o_hierarchy_line_part", 2);
        assert.containsNone(target, ".o_hierarchy_line_left");
        assert.containsNone(target, ".o_hierarchy_line_right");
        assert.containsOnce(target, ".o_hierarchy_node_container");
        assert.containsOnce(target, ".o_hierarchy_node");
        assert.containsNone(target, ".o_hierarchy_node_button.btn-secondary");
        assert.containsOnce(target, ".o_hierarchy_node_button");
        assert.containsOnce(target, ".o_hierarchy_node_container:not(.o_hierarchy_node_button)");
        assert.deepEqual(getNodesTextContent(target.querySelectorAll(".o_hierarchy_row .o_hierarchy_node_content")), ["Albert"]);
    });

    QUnit.test("display the parent above the line when many records on the parent row", async function (assert) {
        serverData.models["hr.employee"].records.push({
            name: "Alfred",
            parent_id: false,
            child_ids: [],
        })
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
        });

        assert.containsOnce(target, ".o_hierarchy_row");
        assert.containsNone(target, ".o_hierarchy_separator");
        assert.containsN(target, ".o_hierarchy_node", 2);
        assert.containsOnce(target, ".o_hierarchy_node_button.btn-primary");
        await click(target, ".o_hierarchy_node_button.btn-primary");
        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsOnce(target, ".o_hierarchy_separator");
        assert.containsOnce(target, ".o_hierarchy_line_left");
        assert.containsOnce(target, ".o_hierarchy_line_right");
        assert.containsOnce(target, ".o_hierarchy_parent_node_container");
        assert.strictEqual(target.querySelector(".o_hierarchy_parent_node_container").textContent, "Albert");
    });

    QUnit.test("search record in hierarchy view", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            domain: [["id", "=", 4]], // simulate a search
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 2);
        assert.containsN(target, ".o_hierarchy_separator", 1);
        assert.containsOnce(target, ".o_hierarchy_node_highlighted");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_highlighted").textContent.trim(), "LouisJosephine");
    });

    QUnit.test("search record in hierarchy view with child field name defined in the arch", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            viewId: 1,
            serverData,
            domain: [["id", "=", 4]], // simulate a search
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 2);
        assert.containsN(target, ".o_hierarchy_separator", 1);
        assert.containsOnce(target, ".o_hierarchy_node_highlighted");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_highlighted").textContent.trim(), "LouisJosephine");
    });

    QUnit.test("fetch parent record", async function (assert) {
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            domain: [["id", "=", 4]], // simulate a search
        });

        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 2);
        assert.containsN(target, ".o_hierarchy_separator", 1);
        assert.containsOnce(target, ".o_hierarchy_node_highlighted");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_highlighted").textContent.trim(), "LouisJosephine");
        let rows = target.querySelectorAll(".o_hierarchy_row");
        let row = rows[0];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "JosephineAlbert");
        row = rows[1];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "LouisJosephine");
        assert.containsOnce(
            target,
            ".o_hierarchy_node_container button .fa-chevron-up",
            "Button to fetch the parent node should be visible on the first node displayed in the view."
        );
        await click(target, ".o_hierarchy_node_container button .fa-chevron-up");
        assert.containsN(target, ".o_hierarchy_row", 3);
        assert.containsN(target, ".o_hierarchy_node", 4);
        assert.containsN(target, ".o_hierarchy_separator", 2);
        assert.containsOnce(target, ".o_hierarchy_node_highlighted");
        assert.strictEqual(target.querySelector(".o_hierarchy_node_highlighted").textContent.trim(), "LouisJosephine");
        rows = target.querySelectorAll(".o_hierarchy_row");
        row = rows[0];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "Albert");
        row = rows[1];
        assert.containsN(row, ".o_hierarchy_node", 2);
        assert.deepEqual(
            getNodesTextContent(row.querySelectorAll(".o_hierarchy_node_content")),
            ["GeorgesAlbert", "JosephineAlbert"],
        );
        row = rows[2];
        assert.containsOnce(row, ".o_hierarchy_node");
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "LouisJosephine");
    });

    QUnit.test("fetch parent when there are many records without the same parent in the same row", async function (assert) {
        serverData.models["hr.employee"].records.push(
            { id: 5, name: "Lisa", parent_id: 2, child_ids: []},
        );
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            domain: [["name", "ilike", "l"]], // simulate a search
        });
        assert.containsOnce(target, ".o_hierarchy_row");
        assert.containsN(target, ".o_hierarchy_node_container", 3);
        assert.deepEqual(
            getNodesTextContent(target.querySelectorAll(".o_hierarchy_node_content")),
            [
                "LisaGeorges", "LouisJosephine", "Albert",
            ],
        );
        assert.containsN(target, ".o_hierarchy_node_container button .fa-chevron-up", 2);
        const firstNode = target.querySelector(".o_hierarchy_node_container");
        await click(firstNode, ".o_hierarchy_node_container button .fa-chevron-up");
        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 2);
        assert.deepEqual(
            getNodesTextContent(target.querySelectorAll(".o_hierarchy_node_content")),
            [
                "GeorgesAlbert", "LisaGeorges",
            ],
        );
        assert.containsOnce(target, ".o_hierarchy_node_container button .fa-chevron-up");
        await click(target, ".o_hierarchy_node_container button .fa-chevron-up");
        assert.containsN(target, ".o_hierarchy_row", 3);
        assert.containsN(target, ".o_hierarchy_node", 4);
    });

    QUnit.test("fetch parent when parent record is in the same row", async function (assert) {
        serverData.models["hr.employee"].records.push(
            { id: 5, name: "Lisa", parent_id: 2, child_ids: []},
        );
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            domain: [["id", "in", [1, 2, 3, 4, 5]]], // simulate a search
        });
        assert.containsOnce(target, ".o_hierarchy_row");
        assert.containsN(target, ".o_hierarchy_node_container", 5);
        assert.containsN(target, ".o_hierarchy_node_container button .fa-chevron-up", 4);
        const firstNodeWithParentBtn = target.querySelector(".o_hierarchy_node_container:has(button .fa-chevron-up)");
        await click(firstNodeWithParentBtn, ".o_hierarchy_node_container button .fa-chevron-up");
        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 3);
        assert.deepEqual(
            getNodesTextContent(target.querySelectorAll(".o_hierarchy_node_content")),
            [
                "Albert", "GeorgesAlbert", "JosephineAlbert",
            ],
        );
    });

    QUnit.test("fetch parent of node with children displayed", async function (assert) {
        serverData.models["hr.employee"].records.push(
            { id: 5, name: "Lisa", parent_id: 2, child_ids: []},
        );
        serverData.models["hr.employee"].records.find((rec) => rec.id === 2).child_ids.push(5);
        await makeView({
            type: "hierarchy",
            resModel: "hr.employee",
            serverData,
            domain: [["id", "in", [1, 2, 3, 4, 5]]], // simulate a search
        });
        assert.containsOnce(target, ".o_hierarchy_row");
        assert.containsN(target, ".o_hierarchy_node_container", 5);
        assert.containsN(target, ".o_hierarchy_node_container button .fa-chevron-up", 4);
        const georgesNode = target.querySelector(".o_hierarchy_node_container:has(button[name=hierarchy_search_parent_node])");
        assert.strictEqual(georgesNode.querySelector(".o_hierarchy_node_content").textContent, "GeorgesAlbert");
        await click(georgesNode, "button[name=hierarchy_search_subsidiaries]");
        assert.containsN(target, ".o_hierarchy_row", 2);
        assert.containsN(target, ".o_hierarchy_node", 5);
        const rows = target.querySelectorAll(".o_hierarchy_row");
        let row = rows[0];
        assert.containsN(row, ".o_hierarchy_node", 4);
        assert.deepEqual(
            getNodesTextContent(row.querySelectorAll(".o_hierarchy_node_content")),
            ["Albert", "GeorgesAlbert", "JosephineAlbert", "LouisJosephine"],
        );
        row = rows[1];
        assert.containsN(row, ".o_hierarchy_node", 1);
        assert.strictEqual(row.querySelector(".o_hierarchy_node_content").textContent, "LisaGeorges");
        const firstNodeWithParentBtn = target.querySelector(".o_hierarchy_node_container:has(button .fa-chevron-up)");
        await click(firstNodeWithParentBtn, ".o_hierarchy_node_container button .fa-chevron-up");
        assert.containsN(target, ".o_hierarchy_row", 3);
        assert.containsN(target, ".o_hierarchy_node", 4);
    });

    QUnit.skip("Test cyclic hierarchy", async function (assert) {
        // TODO
    });
});
