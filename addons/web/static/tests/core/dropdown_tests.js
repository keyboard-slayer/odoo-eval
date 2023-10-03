/** @odoo-module **/

import { Component, xml, onMounted, onPatched, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { DropdownGroup } from "@web/core/dropdown/dropdown_group";
import { hotkeyService } from "@web/core/hotkeys/hotkey_service";
import { overlayService } from "@web/core/overlay/overlay_service";
import { registry } from "@web/core/registry";
import { uiService } from "@web/core/ui/ui_service";
import { makeTestEnv } from "../helpers/mock_env";
import { makeFakeLocalizationService } from "../helpers/mock_services";
import { mountInFixture } from "../helpers/mountInFixture";
import {
    click,
    getFixture,
    makeDeferred,
    mouseEnter,
    nextTick,
    patchWithCleanup,
    triggerEvent,
    triggerHotkey,
} from "../helpers/utils";
import { getPickerCell } from "./datetime/datetime_test_helpers";
import { datetimePickerService } from "@web/core/datetime/datetimepicker_service";
import { popoverService } from "@web/core/popover/popover_service";

const serviceRegistry = registry.category("services");

let env;
let target;

const DROPDOWN_TOGGLE = ".o-dropdown.dropdown-toggle";
const DROPDOWN_MENU = ".o-dropdown--menu.dropdown-menu";
const DROPDOWN_ITEM = ".o-dropdown-item.dropdown-item:not(.o-dropdown)";

async function openDropdown(target, selector = DROPDOWN_TOGGLE) {
    await click(target, selector);
}

function simpleDropdown(options = {}) {
    class SimpleDropdown extends Component {
        static components = { Dropdown, DropdownItem };
        static template = xml`
            <div class="outside">outside</div>
            <Dropdown t-props="dropdownProps">
                <button>Dropdown</button>
                <t t-set-slot="content">
                    <DropdownItem class="'item-a'">Item A</DropdownItem>
                    <DropdownItem class="'item-b'">Item B</DropdownItem>
                    <DropdownItem class="'item-c'">Item C</DropdownItem>
                </t>
            </Dropdown>
        `;

        setup() {
            this.dropdownProps = useState({});
            options.setup?.call(this);
        }
    }
    return SimpleDropdown;
}

function multiLevelDropdown(options = {}) {
    class MultiLevelDropdown extends Component {
        static components = { Dropdown, DropdownItem };
        static template = xml`
            <div class="outside">outside</div>
            <Dropdown t-props="dropdownProps">
                <button class="dropdown-a">A</button>
                <t t-set-slot="content">
                    <DropdownItem class="'item-a'">Item A</DropdownItem>
                    <Dropdown t-props="dropdownProps">
                        <button class="dropdown-b">B</button>
                        <t t-set-slot="content">
                            <DropdownItem class="'item-b'">Item B</DropdownItem>
                            <Dropdown t-props="dropdownProps">
                                <button class="dropdown-c">C</button>
                                <t t-set-slot="content">
                                    <DropdownItem class="'item-c'">Item C</DropdownItem>
                                </t>
                            </Dropdown>
                        </t>
                    </Dropdown>
                </t>
            </Dropdown>
        `;

        setup() {
            this.dropdownProps = {};
            options.setup?.call(this);
        }
    }
    return MultiLevelDropdown;
}

function startOpenState() {
    const state = useState({
        isOpen: true,
        open: () => {
            state.isOpen = true;
        },
        close: () => {
            state.isOpen = false;
        },
    });
    return state;
}

QUnit.module("Components", ({ beforeEach }) => {
    beforeEach(async () => {
        serviceRegistry.add("hotkey", hotkeyService);
        serviceRegistry.add("ui", uiService);
        serviceRegistry.add("overlay", overlayService);
        serviceRegistry.add("popover", popoverService);
        target = getFixture();
        patchWithCleanup(browser, {
            setTimeout: (fn) => fn(),
            clearTimeout: () => {},
        });
    });

    QUnit.module("Dropdown");

    QUnit.test("can be rendered", async (assert) => {
        await mountInFixture(simpleDropdown(), target);

        assert.containsOnce(target, DROPDOWN_TOGGLE);
        assert.containsNone(target, DROPDOWN_MENU);

        const toggle = target.querySelector(DROPDOWN_TOGGLE);
        assert.strictEqual(toggle.className, "o-dropdown dropdown-toggle");
        assert.strictEqual(toggle.ariaExpanded, "false");
    });

    QUnit.test("can be styled", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown menuClass="'test-menu'">
                    <button class="test-toggler">Coucou</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'test-dropdown-item'"/>
                    </t>
                </Dropdown>
            `;
        }

        await mountInFixture(Parent, target);
        assert.hasClass(target.querySelector(DROPDOWN_TOGGLE), "test-toggler");

        await openDropdown(target);
        assert.hasClass(target.querySelector(DROPDOWN_MENU), "test-menu");
        assert.hasClass(target.querySelector(DROPDOWN_ITEM), "test-dropdown-item");
    });

    QUnit.test("menu can be toggled", async (assert) => {
        const beforeOpenProm = makeDeferred();
        const Parent = simpleDropdown({
            setup() {
                this.dropdownProps.beforeOpen = () => {
                    assert.step("beforeOpen");
                    return beforeOpenProm;
                };
            },
        });

        await mountInFixture(Parent, target);

        await click(target, DROPDOWN_TOGGLE);
        assert.verifySteps(["beforeOpen"]);
        assert.containsNone(target, DROPDOWN_MENU);
        assert.strictEqual(target.querySelector(DROPDOWN_TOGGLE).ariaExpanded, "false");
        beforeOpenProm.resolve();
        await nextTick();

        assert.containsOnce(target, DROPDOWN_MENU);
        assert.strictEqual(target.querySelector(DROPDOWN_MENU).getAttribute("role"), "menu");
        assert.strictEqual(target.querySelector(DROPDOWN_TOGGLE).ariaExpanded, "true");

        await click(target, DROPDOWN_TOGGLE);
        assert.containsNone(target, DROPDOWN_MENU);
        assert.strictEqual(target.querySelector(DROPDOWN_TOGGLE).ariaExpanded, "false");
    });

    QUnit.test("initial open state can be true", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <div class="outside">outside</div>
                <Dropdown state="dropdown">
                    <button>Dropdown</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'item-a'">Item A</DropdownItem>
                        <DropdownItem class="'item-b'">Item B</DropdownItem>
                        <DropdownItem class="'item-c'">Item C</DropdownItem>
                    </t>
                </Dropdown>
            `;

            setup() {
                this.dropdown = startOpenState();
            }
        }

        await mountInFixture(Parent, target);
        await nextTick();
        assert.containsOnce(target, DROPDOWN_MENU);
    });

    QUnit.test("close on outside click", async (assert) => {
        await mountInFixture(simpleDropdown(), target);

        await openDropdown(target);
        assert.containsOnce(target, DROPDOWN_MENU);
        await click(target, "div.outside");
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU);
    });

    QUnit.test("close on item selection", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button>Coucou</button>
                    <t t-set-slot="content">
                        <DropdownItem>Item</DropdownItem>
                    </t>
                </Dropdown>
            `;
        }
        await mountInFixture(Parent, target);

        await openDropdown(target);
        await click(target, DROPDOWN_ITEM);
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU);
    });

    QUnit.test("'o-dropdown-caret' class adds a caret", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button class="first o-dropdown-caret" data-hotkey="1">First</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'first-first'">O</DropdownItem>
                        <Dropdown>
                            <button class="second o-dropdown-no-caret">Second</button>
                            <t t-set-slot="content">
                                <DropdownItem class="'second-first'">O</DropdownItem>
                            </t>
                        </Dropdown>
                    </t>
                </Dropdown>
            `;
        }
        await mountInFixture(Parent, target);

        const getContent = (selector) => {
            const element = target.querySelector(selector);
            const styles = window.getComputedStyle(element, "::after");
            return styles.content;
        };

        assert.notEqual(getContent(".first"), "none", "first dropdown should have a caret");

        await openDropdown(target);
        assert.equal(getContent(".second"), "none", "second dropdown should not have a caret");
    });

    QUnit.test("onOpened callback props called after the menu has been mounted", async (assert) => {
        const beforeOpenProm = makeDeferred();
        class Parent extends Component {
            static template = xml`
                <Dropdown onOpened.bind="onOpenedCallback" beforeOpen.bind="beforeOpenCallback">
                    <button>Open</button>
                    <t t-set-slot="content">Coucou</t>
                </Dropdown>
            `;
            static components = { Dropdown, DropdownItem };
            beforeOpenCallback() {
                assert.step("beforeOpened");
                return beforeOpenProm;
            }
            onOpenedCallback() {
                assert.step("onOpened");
            }
        }
        await mountInFixture(Parent, target);
        await click(target, DROPDOWN_TOGGLE);
        assert.verifySteps(["beforeOpened"]);
        beforeOpenProm.resolve();
        await nextTick();
        assert.verifySteps(["onOpened"]);
    });

    QUnit.test("dropdown button can be disabled", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown };
            static template = xml`
                <Dropdown>
                    <button disabled="">Open</button>
                    <t t-set-slot="content">
                        Coucou
                    </t>
                </Dropdown>
            `;
        }
        await mountInFixture(Parent, target);
        assert.strictEqual(Boolean(target.querySelector(DROPDOWN_TOGGLE).disabled), true);
    });

    QUnit.test("multi-level dropdown: can be rendered and toggled", async (assert) => {
        await mountInFixture(multiLevelDropdown(), target);

        await click(target, ".dropdown-a");
        await nextTick();
        await mouseEnter(target, ".dropdown-b");
        await nextTick();
        await mouseEnter(target, ".dropdown-c");
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 3);
        assert.equal(1, 1);
    });

    QUnit.test("multi-level dropdown: initial open state can be true", async (assert) => {
        const Parent = multiLevelDropdown({
            setup() {
                this.dropdownProps.state = useState({
                    isOpen: true,
                    open: () => {},
                    close: () => {},
                    toggle: () => {},
                });
            },
        });

        await mountInFixture(Parent, target, { env });
        await nextTick(); // Wait for each dropdown to update its state
        await nextTick();
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 3);
    });

    QUnit.test("multi-level dropdown: close on outside click", async (assert) => {
        await mountInFixture(multiLevelDropdown(), target);

        await click(target, ".dropdown-a");
        await nextTick();
        await mouseEnter(target, ".dropdown-b");
        await nextTick();
        await mouseEnter(target, ".dropdown-c");
        await nextTick();

        assert.containsN(target, DROPDOWN_MENU, 3);
        await click(target, "div.outside");
        assert.containsNone(target, DROPDOWN_MENU);
    });

    QUnit.test("multi-level dropdown: close on item selection", async (assert) => {
        await mountInFixture(multiLevelDropdown(), target);

        await openDropdown(target, ".dropdown-a");
        await nextTick();
        await mouseEnter(target, ".dropdown-b");
        await nextTick();

        assert.containsN(target, DROPDOWN_MENU, 2);
        assert.containsN(target, DROPDOWN_ITEM, 2);

        await click(target, ".o-dropdown-item.item-b");
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU);
    });

    QUnit.test("multi-level dropdown: parent closing modes on item selection", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <div class="outside">outside</div>
                <Dropdown>
                    <button class="dropdown-a">Dropdown A</button>
                    <t t-set-slot="content">
                        <Dropdown>
                            <button class="dropdown-b">Dropdown B</button>
                            <t t-set-slot="content">
                                <DropdownItem class="'item1'" closingMode="'none'">A</DropdownItem>
                                <DropdownItem class="'item2'" closingMode="'closest'">B</DropdownItem>
                                <DropdownItem class="'item3'" closingMode="'all'">C</DropdownItem>
                                <DropdownItem class="'item4'">D</DropdownItem>
                            </t>
                        </Dropdown>
                    </t>
                </Dropdown>
            `;
        }
        await mountInFixture(Parent, target);

        // Open the 2-level dropdowns
        await click(target, ".dropdown-a");
        await nextTick();
        await mouseEnter(target, ".dropdown-b");
        await nextTick();

        // Select item (closingMode=none)
        await click(target, ".item1");
        assert.containsN(target, DROPDOWN_MENU, 2);

        // Select item (closingMode=closest)
        await click(target, ".item2");
        assert.containsN(target, DROPDOWN_MENU, 1);

        // Reopen second level dropdown
        await mouseEnter(target, ".dropdown-b");

        // Select item (closingMode=all)
        await click(target, ".item3");
        assert.containsNone(target, DROPDOWN_MENU);

        // Reopen the 2-level dropdowns
        await click(target, ".dropdown-a");
        await nextTick();
        await mouseEnter(target, ".dropdown-b");
        await nextTick();

        // Select item (default should be closingMode=all)
        await click(target, ".item4");
        assert.containsNone(target, DROPDOWN_MENU);
    });

    QUnit.test("multi-level dropdown: recursive template can be rendered", async (assert) => {
        class Parent extends Component {
            static template = "recursive.Template";
            static components = { Dropdown, DropdownItem };
            setup() {
                this.dropdown = startOpenState();

                this.name = "foo";
                this.items = [
                    {
                        name: "foo-0",
                        children: [
                            { name: "foo-00", children: [] },
                            {
                                name: "foo-01",
                                children: [
                                    { name: "foo-010", children: [] },
                                    { name: "foo-011", children: [] },
                                    {
                                        name: "foo-012",
                                        children: [
                                            { name: "foo-0120", children: [] },
                                            { name: "foo-0121", children: [] },
                                            { name: "foo-0122", children: [] },
                                        ],
                                    },
                                ],
                            },
                            { name: "foo-02", children: [] },
                        ],
                    },
                    { name: "foo-1", children: [] },
                    { name: "foo-2", children: [] },
                ];
            }
        }

        await mountInFixture(Parent, target, {
            templates: `<t t-name="recursive.Template">
                <Dropdown state="dropdown">
                    <button><t t-esc="name" /></button>
                    <t t-set-slot="content">
                        <t t-foreach="items" t-as="item" t-key="item_index">

                        <t t-if="!item.children.length">
                            <DropdownItem><t t-esc="item.name"/></DropdownItem>
                        </t>

                        <t t-else="" t-call="recursive.Template">
                            <t t-set="name" t-value="item.name" />
                            <t t-set="items" t-value="item.children" />
                        </t>

                        </t>
                    </t>
                </Dropdown>
            </t>`,
        });

        // Each sub-dropdown needs a tick to open
        await nextTick();
        await nextTick();
        await nextTick();
        await nextTick();

        assert.deepEqual(
            [...target.querySelectorAll(".dropdown-toggle, .dropdown-menu > .dropdown-item")].map(
                (el) => el.textContent
            ),
            [
                "foo",
                "foo-0",
                "foo-1",
                "foo-2",
                "foo-00",
                "foo-01",
                "foo-02",
                "foo-010",
                "foo-011",
                "foo-012",
                "foo-0120",
                "foo-0121",
                "foo-0122",
            ]
        );
    });

    QUnit.test("dropdowns keynav", async (assert) => {
        assert.expect(41);
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button data-hotkey="m">Toggle</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'item1'" onSelected="() => onItemSelected(1)">item1</DropdownItem>
                        <DropdownItem class="'item2'" attrs="{ 'data-hotkey': '2'}" onSelected="() => onItemSelected(2)">item2</DropdownItem>
                        <DropdownItem class="'item3'" onSelected="() => onItemSelected(3)">item3</DropdownItem>
                    </t>
                </Dropdown>
            `;
            onItemSelected(value) {
                assert.step(value.toString());
            }
        }
        await mountInFixture(Parent, target);
        assert.containsNone(target, ".dropdown-menu", "menu is closed at start");

        triggerHotkey("m", true);
        await nextTick();
        assert.containsOnce(
            target,
            ".dropdown-menu",
            "menu is opened after pressing the toggler hotkey"
        );

        // Navigate with arrows
        assert.containsNone(
            target,
            ".dropdown-menu > .focus",
            "menu should not have any active items"
        );

        const scenarioSteps = [
            { hotkey: "arrowdown", expected: "item1" },
            { hotkey: "arrowdown", expected: "item2" },
            { hotkey: "arrowdown", expected: "item3" },
            { hotkey: "arrowdown", expected: "item1" },
            { hotkey: "tab", expected: "item2" },
            { hotkey: "tab", expected: "item3" },
            { hotkey: "tab", expected: "item1" },
            { hotkey: "arrowup", expected: "item3" },
            { hotkey: "arrowup", expected: "item2" },
            { hotkey: "arrowup", expected: "item1" },
            { hotkey: "shift+tab", expected: "item3" },
            { hotkey: "shift+tab", expected: "item2" },
            { hotkey: "shift+tab", expected: "item1" },
            { hotkey: "end", expected: "item3" },
            { hotkey: "home", expected: "item1" },
        ];

        for (const step of scenarioSteps) {
            triggerHotkey(step.hotkey);
            await nextTick();
            assert.hasClass(target.querySelector(".dropdown-menu > .focus"), step.expected);
            assert.strictEqual(
                document.activeElement,
                target.querySelector(".dropdown-menu > .focus")
            );
        }

        // Select last one activated in previous scenario (item1)
        triggerHotkey("enter");
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU, "menu is closed after item selection");

        // Reopen dropdown
        triggerHotkey("m", true);
        await nextTick();
        assert.containsOnce(
            target,
            DROPDOWN_MENU,
            "menu is opened after pressing the toggler hotkey"
        );

        // Select second item through data-hotkey attribute
        triggerHotkey("2", true);
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU, "menu is closed after item selection");

        // Reopen dropdown
        triggerHotkey("m", true);
        await nextTick();
        assert.containsOnce(
            target,
            DROPDOWN_MENU,
            "menu is opened after pressing the toggler hotkey"
        );

        // Close dropdown with keynav
        triggerHotkey("escape");
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU, "menu is closed after item selection");

        assert.verifySteps(["1", "2"], "items should have been selected in this order");
    });

    QUnit.test("dropdowns keynav is not impacted by bootstrap", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown };
            static template = xml`
                <Dropdown state="dropdown">
                    <button>Open</button>
                    <t t-set-slot="content">
                        <select><option>foo</option></select>
                    </t>
                </Dropdown>
            `;

            setup() {
                this.dropdown = startOpenState();
            }
        }
        await mountInFixture(Parent, target);
        await nextTick();
        await nextTick();

        assert.containsOnce(target, DROPDOWN_MENU, "menu is opened at start");
        const menu = target.querySelector(DROPDOWN_MENU);

        // This class presence makes bootstrap ignore the below event
        assert.hasClass(menu, "o-dropdown--menu");

        const select = menu.querySelector("select");
        let ev = new KeyboardEvent("keydown", {
            bubbles: true,
            // Define the ArrowDown key with standard API (for hotkey_service)
            key: "ArrowDown",
            code: "ArrowDown",
            // Define the ArrowDown key with deprecated API (for bootstrap)
            keyCode: 40,
            which: 40,
        });
        select.dispatchEvent(ev);
        await nextTick();
        await nextTick();

        ev = new KeyboardEvent("keydown", {
            bubbles: true,
            // Define the ESC key with standard API (for hotkey_service)
            key: "Escape",
            code: "Escape",
            // Define the ESC key with deprecated API (for bootstrap)
            keyCode: 27,
            which: 27,
        });
        select.dispatchEvent(ev);
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU, "menu is now closed");
    });

    QUnit.test("refocus toggler on close with keynav", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <div>
                    <Dropdown>
                        <button class="my_custom_toggler">
                            Click Me
                        </button>
                        <t t-set-slot="content">
                            <DropdownItem>Element 1</DropdownItem>
                            <DropdownItem>Element 2</DropdownItem>
                        </t>
                    </Dropdown>
                </div>
            `;
        }

        await mountInFixture(Parent, target);

        assert.strictEqual(document.activeElement, document.body);

        target.querySelector(".my_custom_toggler").focus(); // mocks a real click flow
        await click(target, ".my_custom_toggler");
        assert.strictEqual(document.activeElement, target.querySelector(".my_custom_toggler"));

        triggerHotkey("ArrowDown");
        await nextTick();
        assert.strictEqual(
            document.activeElement,
            target.querySelector(".dropdown-item:first-child")
        );

        triggerHotkey("Escape");
        await nextTick();
        assert.strictEqual(document.activeElement, target.querySelector(".my_custom_toggler"));
    });

    QUnit.test("multi-level dropdown: keynav", async (assert) => {
        assert.expect(212);
        class Parent extends Component {
            onItemSelected(value) {
                assert.step(value);
            }
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button class="first" data-hotkey="1">First</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'first-first'" onSelected="() => onItemSelected('first-first')">O</DropdownItem>
                        <Dropdown>
                            <button class="second">Second</button>
                            <t t-set-slot="content">
                                <DropdownItem class="'second-first'" onSelected="() => onItemSelected('second-first')">O</DropdownItem>
                                <Dropdown>
                                    <button class="third">Third</button>
                                    <t t-set-slot="content">
                                        <DropdownItem class="'third-first'" onSelected="() => onItemSelected('third-first')">O</DropdownItem>
                                        <DropdownItem class="'third-last'" onSelected="() => onItemSelected('third-last')">O</DropdownItem>
                                    </t>
                                </Dropdown>
                                <DropdownItem class="'second-last'" onSelected="() => onItemSelected('second-last')">O</DropdownItem>
                            </t>
                        </Dropdown>
                        <DropdownItem class="'first-last'" onSelected="() => onItemSelected('first-last')">O</DropdownItem>
                    </t>
                </Dropdown>
            `;
        }
        await mountInFixture(Parent, target);
        assert.containsNone(target, DROPDOWN_MENU, "menus are closed at start");

        // Highlighting and selecting items
        const scenarioSteps = [
            { hotkey: "alt+1" },
            { hotkey: "arrowup", highlighted: ["first-last"] },
            { hotkey: "arrowup", highlighted: ["second"] },
            { hotkey: "arrowdown", highlighted: ["first-last"] },
            { hotkey: "arrowdown", highlighted: ["first-first"] },
            { hotkey: "arrowdown", highlighted: ["second"] },
            { hotkey: "tab", highlighted: ["first-last"] },
            { hotkey: "tab", highlighted: ["first-first"] },
            { hotkey: "tab", highlighted: ["second"] },
            { hotkey: "shift+tab", highlighted: ["first-first"] },
            { hotkey: "shift+tab", highlighted: ["first-last"] },
            { hotkey: "shift+tab", highlighted: ["second"] },
            { hotkey: "arrowright", highlighted: ["second", "second-first"] },
            { hotkey: "arrowright", highlighted: ["second", "second-first"] },
            { hotkey: "arrowleft", highlighted: ["second"] },
            { hotkey: "arrowleft", highlighted: ["second"] },
            { hotkey: "arrowright", highlighted: ["second", "second-first"] },
            { hotkey: "arrowup", highlighted: ["second", "second-last"] },
            { hotkey: "arrowup", highlighted: ["second", "third"] },
            { hotkey: "arrowup", highlighted: ["second", "second-first"] },
            { hotkey: "arrowdown", highlighted: ["second", "third"] },
            { hotkey: "arrowright", highlighted: ["second", "third", "third-first"] },
            { hotkey: "arrowright", highlighted: ["second", "third", "third-first"] },
            { hotkey: "arrowleft", highlighted: ["second", "third"] },
            { hotkey: "arrowleft", highlighted: ["second"] },
            { hotkey: "arrowleft", highlighted: ["second"] },
            { hotkey: "arrowright", highlighted: ["second", "second-first"] },
            { hotkey: "arrowdown", highlighted: ["second", "third"] },
            { hotkey: "arrowright", highlighted: ["second", "third", "third-first"] },
            { hotkey: "arrowup", highlighted: ["second", "third", "third-last"] },
            { hotkey: "home", highlighted: ["second", "third", "third-first"] },
            { hotkey: "home", highlighted: ["second", "third", "third-first"] },
            { hotkey: "end", highlighted: ["second", "third", "third-last"] },
            { hotkey: "end", highlighted: ["second", "third", "third-last"] },
            { hotkey: "arrowleft", highlighted: ["second", "third"] },
            { hotkey: "enter", highlighted: ["second", "third", "third-first"] },
            { hotkey: "enter", selected: "third-first" },
            { hotkey: "alt+1" },
            { hotkey: "arrowup", highlighted: ["first-last"] },
            { hotkey: "arrowup", highlighted: ["second"] },
            { hotkey: "arrowright", highlighted: ["second", "second-first"] },
            { hotkey: "arrowup", highlighted: ["second", "second-last"] },
            { hotkey: "arrowup", highlighted: ["second", "third"] },
            { hotkey: "arrowright", highlighted: ["second", "third", "third-first"] },
            { hotkey: "escape", highlighted: ["second", "third"] },
            { hotkey: "escape", highlighted: ["second"] },
            { hotkey: "escape", highlighted: [] },
        ];

        for (const [stepIndex, step] of scenarioSteps.entries()) {
            triggerHotkey(step.hotkey);
            await nextTick();
            if (step.highlighted !== undefined) {
                const activeElements = [...target.querySelectorAll(".focus")];
                assert.ok(
                    activeElements.length === step.highlighted.length,
                    `step ${stepIndex}: all active elements to check are found`
                );

                for (let i = 0; i < activeElements.length; i++) {
                    assert.hasClass(activeElements[i], step.highlighted[i]);
                }

                const lastActiveElement = activeElements.slice(-1)[0];
                if (lastActiveElement) {
                    assert.hasClass(lastActiveElement, step.highlighted.slice(-1)[0]);
                    assert.strictEqual(
                        document.activeElement,
                        lastActiveElement.classList.contains("dropdown")
                            ? lastActiveElement.querySelector(":scope > .dropdown-toggle")
                            : lastActiveElement
                    );
                } else {
                    // no active element means that the main dropdown is closed
                    assert.hasClass(document.activeElement, "first");
                }
            }
            if (step.selected !== undefined) {
                const verify = step.selected === false ? [] : [step.selected];
                assert.verifySteps(verify, `step ${stepIndex}: selected item is correct`);
            }
        }
    });

    QUnit.test("multi-level dropdown: keynav when rtl direction", async (assert) => {
        assert.expect(10);
        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button class="first" data-hotkey="1">First</button>
                    <t t-set-slot="content">
                        <DropdownItem class="'first-first'">O</DropdownItem>
                        <Dropdown>
                            <button class="second">Second</button>
                            <t t-set-slot="content">
                                <DropdownItem class="'second-first'">O</DropdownItem>
                            </t>
                        </Dropdown>
                    </t>
                </Dropdown>
            `;
        }
        serviceRegistry.add("localization", makeFakeLocalizationService({ direction: "rtl" }));
        await mountInFixture(Parent, target);
        assert.containsNone(target, DROPDOWN_MENU, "menus are closed at start");

        // Highlighting and selecting items
        const scenarioSteps = [
            { hotkey: "alt+1" },
            { hotkey: "arrowdown", highlighted: ["first-first"] },
            { hotkey: "arrowdown", highlighted: ["second"] },
            { hotkey: "arrowleft", highlighted: ["second", "second-first"] },
            { hotkey: "arrowright", highlighted: ["second"] },
        ];

        for (const [stepIndex, step] of scenarioSteps.entries()) {
            triggerHotkey(step.hotkey);
            await nextTick();
            if (step.highlighted !== undefined) {
                const activeElements = [...target.querySelectorAll(".focus")];
                assert.ok(
                    activeElements.length === step.highlighted.length,
                    `step ${stepIndex}: all active elements to check are found`
                );

                for (let i = 0; i < activeElements.length; i++) {
                    assert.hasClass(activeElements[i], step.highlighted[i]);
                }
            }
        }
    });

    QUnit.test("multi-level dropdown: submenu keeps position when patched", async (assert) => {
        assert.expect(9);
        patchWithCleanup(Dropdown.prototype, {
            setup() {
                super.setup(...arguments);
                if (this.hasParent) {
                    onMounted(() => {
                        assert.step(`submenu mounted`);
                    });
                    let previousMenuRect;
                    onPatched(() => {
                        assert.step(`submenu patched`);
                        if (this.state.isOpen && this.menuRef.el) {
                            const subMenuRect = this.menuRef.el.getBoundingClientRect();
                            if (previousMenuRect) {
                                assert.strictEqual(subMenuRect.top, previousMenuRect.top);
                                assert.strictEqual(subMenuRect.left, previousMenuRect.left);
                            }
                            previousMenuRect = subMenuRect;
                        }
                    });
                }
            },
        });
        let parentState;
        class Parent extends Component {
            setup() {
                this.state = useState({ foo: false });
                parentState = this.state;
            }
        }
        Parent.template = xml`
            <Dropdown>
                <button class="one">one</button>
                <t t-set-slot="content">
                    <Dropdown>
                        <button class="two">two</button>
                        <t t-set-slot="content">
                            <DropdownItem t-if="state.foo" class="three">three</DropdownItem>
                        </t>
                    </Dropdown>
                </t>
            </Dropdown>
        `;
        Parent.components = { Dropdown, DropdownItem };

        env = await makeTestEnv();
        await mountInFixture(Parent, target, { env });
        assert.verifySteps([]);

        // Open the menu
        await click(target, ".one.dropdown-toggle");
        assert.verifySteps(["submenu mounted"]);

        // Open the submenu
        await triggerEvent(target, ".two.dropdown-toggle", "mouseenter");
        await nextTick();
        assert.verifySteps(["submenu patched"]);

        // Change submenu content
        parentState.foo = true;
        await nextTick();
        assert.verifySteps(["submenu patched"]);
    });

    QUnit.test("showCaret props adds caret class", async (assert) => {
        class Parent extends Component {}
        Parent.template = xml`
            <Dropdown class="'first'" hotkey="'1'" showCaret="true">
                <DropdownItem class="'first-first'">O</DropdownItem>
                <Dropdown class="'second'" showCaret="false">
                    <DropdownItem class="'second-first'">O</DropdownItem>
                </Dropdown>
            </Dropdown>
        `;
        Parent.components = { Dropdown, DropdownItem };
        env = await makeTestEnv();
        await mount(Parent, target, { env });
        assert.containsNone(
            target,
            ".first.o-dropdown--no-caret",
            "first dropdown should have a caret"
        );
        await click(target, ".dropdown-toggle");
        assert.containsOnce(
            target,
            ".second.o-dropdown--no-caret",
            "second dropdown should not have a caret"
        );
    });

    QUnit.test("caret should be repositioned to default direction when closed", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown };
            static template = xml`
                <div style="height: 384px;"/> <!-- filler: takes half the runbot's browser_size -->
                <Dropdown showCaret="true">
                    <t t-set-slot="toggler">🍋</t>
                    <div style="height: 400px; width: 50px;"/> <!-- menu filler -->
                </Dropdown>
            `;
        }
        // The fixture should be shown for this test, as the positioning container is the html node
        target.style.position = "fixed";
        target.style.top = "0";
        target.style.left = "0";

        env = await makeTestEnv();
        await mount(Parent, target, { env });
        const dropdown = target.querySelector(".o-dropdown");
        assert.doesNotHaveClass(dropdown, "show");
        assert.hasClass(dropdown, "dropdown");

        // open
        await click(target, ".dropdown-toggle");
        await nextTick(); // awaits for the caret to get patched
        assert.hasClass(dropdown, "show");
        assert.hasClass(dropdown, "dropend");

        // close
        await click(target, ".dropdown-toggle");
        assert.doesNotHaveClass(dropdown, "show");
        assert.hasClass(dropdown, "dropdown");

        // open
        await click(target, ".dropdown-toggle");
        await nextTick(); // awaits for the caret to get patched
        assert.hasClass(dropdown, "show");
        assert.hasClass(dropdown, "dropend");
    });

    QUnit.test(
        "multi-level dropdown: mouseentering a dropdown item should close any subdropdown",
        async (assert) => {
            assert.expect(4);
            class Parent extends Component {
                static components = { Dropdown, DropdownItem };
                static template = xml`
                    <Dropdown>
                        <button class="main">Main</button>
                        <t t-set-slot="content">
                            <DropdownItem class="'item'">Item</DropdownItem>
                            <Dropdown>
                                <button class="sub">Sub</button>
                                <t t-set-slot="content">
                                    <DropdownItem class="'sub-item'">Sub Item</DropdownItem>
                                </t>
                            </Dropdown>
                        </t>
                    </Dropdown>
                `;
            }
            await mountInFixture(Parent, target);
            assert.containsNone(target, DROPDOWN_MENU, "menus are closed at start");

            // Open main dropdown
            await click(target, ".main");
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU, "1st menu is opened");

            // Mouse enter sub dropdown
            await mouseEnter(target, ".sub");
            await nextTick();
            assert.containsN(target, DROPDOWN_MENU, 2, "all menus are opened");

            // Mouse enter the adjacent dropdown item
            await mouseEnter(target, ".item");
            assert.containsOnce(target, DROPDOWN_MENU, "only 1st menu is opened");
        }
    );

    QUnit.test("multi-level dropdown: unsubscribe all keynav when root close", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown };
            static template = xml`
                <Dropdown>
                    <button class="first">First</button>
                    <t t-set-slot="content">
                        <Dropdown>
                            <button class="second">Second</button>
                            <t t-set-slot="content">
                                <Dropdown>
                                    <button class="third">Third</button>
                                    <t t-set-slot="content">
                                        <p>Coucou</p>
                                    </t>
                                </Dropdown>
                            </t>
                        </Dropdown>
                    </t>
                </Dropdown>
            `;
        }

        const hotkeys = [
            "home",
            "end",
            "tab",
            "shift+tab",
            "arrowdown",
            "arrowup",
            "arrowleft",
            "arrowright",
            "escape",
            "enter",
        ];
        const registeredHotkeys = new Set();
        const removedHotkeys = new Set();

        function checkKeys(keySet) {
            for (const hotkey of hotkeys) {
                assert.ok(keySet.has(hotkey), `${hotkey} is in keySet`);
            }
            keySet.clear();
        }

        env = await makeTestEnv();
        patchWithCleanup(env.services.hotkey, {
            add(key) {
                const remove = super.add(...arguments);
                registeredHotkeys.add(key);
                return () => {
                    remove();
                    removedHotkeys.add(key);
                };
            },
        });
        await mountInFixture(Parent, target, { env });
        assert.containsNone(target, DROPDOWN_MENU, "menus are closed at start");
        assert.strictEqual(registeredHotkeys.size, 0, "no hotkey registered");

        // Open dropdowns one by one
        await click(target, ".first");
        await nextTick();
        assert.containsOnce(target, DROPDOWN_MENU, "1st menu is opened");
        checkKeys(registeredHotkeys);

        await mouseEnter(target, ".second");
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 2, "2nd menu is also opened");
        checkKeys(registeredHotkeys);

        await mouseEnter(target, ".third");
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 3, "3rd menu is also opened");
        checkKeys(registeredHotkeys);

        // Close third
        triggerHotkey("escape");
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 2, "two menus still opened");
        checkKeys(removedHotkeys);

        // Reopen second
        await mouseEnter(target, ".third");
        await nextTick();
        assert.containsN(target, DROPDOWN_MENU, 3, "3rd menu is also opened");
        checkKeys(registeredHotkeys);

        // Close third, second and first
        triggerHotkey("escape");
        await nextTick();
        checkKeys(removedHotkeys);
        triggerHotkey("escape");
        await nextTick();
        checkKeys(removedHotkeys);
        triggerHotkey("escape");
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU, "all menus are now closed");
        checkKeys(removedHotkeys);
    });

    QUnit.test(
        "Dropdown with a date picker inside do not close when a click occurs in date picker",
        async (assert) => {
            registry.category("services").add("datetime_picker", datetimePickerService);
            class Parent extends Component {
                static components = { DateTimeInput, Dropdown };
                static template = xml`
                    <Dropdown>
                    <button>Dropdown toggler</button>
                        <t t-set-slot="content">
                            <DateTimeInput />
                        </t>
                    </Dropdown>
                `;
            }

            await mountInFixture(Parent, target);

            assert.containsNone(target, DROPDOWN_MENU);

            await openDropdown(target);

            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsNone(target, ".o_datetime_picker");
            assert.strictEqual(target.querySelector(".o_datetime_input").value, "");

            await click(target, ".o_datetime_input");

            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsOnce(target, ".o_datetime_picker");
            assert.strictEqual(target.querySelector(".o_datetime_input").value, "");

            await click(getPickerCell("15")); // select some day

            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsOnce(target, ".o_datetime_picker");
            assert.notOk(target.querySelector(".o_datetime_input").value === "");
        }
    );

    QUnit.test("t-if t-else as toggler", async (assert) => {
        let state = undefined;

        class Parent extends Component {
            static components = { Dropdown };
            static template = xml`
                <Dropdown>
                    <button t-if="state.foo === 'bar'">Coucou</button>
                    <a t-else="">ByeBye</a>
                    <t t-set-slot="content">
                        Hello
                    </t>
                </Dropdown>
            `;

            setup() {
                state = useState({ foo: "bar" });
                this.state = state;
            }
        }
        await mountInFixture(Parent, target);
        assert.containsNone(target, DROPDOWN_MENU);

        // Open
        await click(target, DROPDOWN_TOGGLE);
        await nextTick();
        assert.containsOnce(target, DROPDOWN_MENU);

        // Close
        await click(target, DROPDOWN_TOGGLE);
        await nextTick();
        assert.containsNone(target, DROPDOWN_MENU);

        // Change button then open
        state.foo = "boo";
        await nextTick();
        await click(target, DROPDOWN_TOGGLE);
        await nextTick();
        assert.containsOnce(target, DROPDOWN_MENU);
    });

    QUnit.module("DropdownItem");

    QUnit.test("DropdownItem can be rendered as <span/>", async (assert) => {
        class Parent extends Component {
            static components = { DropdownItem };
            static template = xml`<DropdownItem>coucou</DropdownItem>`;
        }
        await mountInFixture(Parent, target);
        assert.strictEqual(
            target.querySelector(".dropdown-item").outerHTML,
            '<span class="o-dropdown-item dropdown-item o-navigable" role="menuitem" tabindex="0">coucou</span>'
        );
    });

    QUnit.test("DropdownItem (with href prop) can be rendered as <a/>", async (assert) => {
        class Parent extends Component {
            static components = { DropdownItem };
            static template = xml`<DropdownItem attrs="{ href: '#' }">coucou</DropdownItem>`;
        }
        await mountInFixture(Parent, target);
        assert.strictEqual(
            target.querySelector(".dropdown-item").outerHTML,
            '<a class="o-dropdown-item dropdown-item o-navigable" role="menuitem" tabindex="0" href="#">coucou</a>'
        );
    });

    QUnit.test("DropdownItem: prevents click default with href", async (assert) => {
        assert.expect(4);
        // A DropdownItem should preventDefault a click as it may take the shape
        // of an <a/> tag with an [href] attribute and e.g. could change the url when clicked.
        patchWithCleanup(DropdownItem.prototype, {
            onClick(ev) {
                assert.ok(!ev.defaultPrevented);
                super.onClick(...arguments);
                const href = ev.target.getAttribute("href");
                // defaultPrevented only if props.href is defined
                assert.ok(href !== null ? ev.defaultPrevented : !ev.defaultPrevented);
            },
        });
        class Parent extends Component {}
        Parent.template = xml`
            <Dropdown>
                <button>Coucou</button>
                <t t-set-slot="content">
                    <DropdownItem class="'link'" attrs="{href: '#'}"/>
                    <DropdownItem class="'nolink'" />
                </t>
            </Dropdown>`;
        Parent.components = { Dropdown, DropdownItem };
        env = await makeTestEnv();
        await mountInFixture(Parent, target, { env });
        // The item containing the link class contains an href prop,
        // which will turn it into <a href=> So it must be defaultPrevented
        // The other one not contain any href props, it must not be defaultPrevented,
        // so as not to prevent the background change flow for example
        await openDropdown(target);
        await click(target, ".link");
        await click(target, "button.dropdown-toggle");
        await click(target, ".nolink");
    });

    QUnit.test("DropdownItem: payload received on item selection", async (assert) => {
        assert.expect(1);

        class Parent extends Component {
            static components = { Dropdown, DropdownItem };
            static template = xml`
                <Dropdown>
                    <button>Open</button>
                    <t t-set-slot="content">
                        <DropdownItem onSelected="() => onItemSelected(42)">Item</DropdownItem>
                    </t>
                </Dropdown>
            `;
            onItemSelected(value) {
                assert.equal(value, 42);
            }
        }
        env = await makeTestEnv();
        await mountInFixture(Parent, target, { env });
        await openDropdown(target);
        await click(target, DROPDOWN_ITEM);
    });

    QUnit.module("DropdownGroup");

    QUnit.test(
        "dropdown groups: when one is open, others with same group name can be toggled on mouse-enter",
        async (assert) => {
            assert.expect(17);
            const beforeOpenProm = makeDeferred();
            class Parent extends Component {
                static components = { Dropdown, DropdownGroup };
                static template = xml`
                    <div>
                        <div class="outside">OUTSIDE</div>
                        <DropdownGroup>
                            <Dropdown menuClass="'menu-one'">
                                <button class="one">One</button>
                                <t t-set-slot="content">
                                    Content One
                                </t>
                            </Dropdown>
                            <Dropdown beforeOpen="() => beforeOpen()" menuClass="'menu-two'">
                                <button class="two">Two</button>
                                <t t-set-slot="content">
                                    Content Two
                                </t>
                            </Dropdown>
                            <Dropdown menuClass="'menu-three'">
                                <button class="three">Three</button>
                                <t t-set-slot="content">
                                    Content Three
                                </t>
                            </Dropdown>
                        </DropdownGroup>
                        <DropdownGroup>
                            <Dropdown menuClass="'menu-four'">
                                <button class="four">Four</button>
                                <t t-set-slot="content">
                                    Content Four
                                </t>
                            </Dropdown>
                        </DropdownGroup>
                    </div>
                `;

                beforeOpen() {
                    assert.step("beforeOpen");
                    return beforeOpenProm;
                }
            }
            await mountInFixture(Parent, target);

            // Click on ONE
            const one = target.querySelector(".one");
            await click(one);
            assert.verifySteps([]);
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.hasClass(one, "show");

            // Hover on TWO
            target.querySelector(".two").dispatchEvent(new MouseEvent("mouseenter"));
            assert.verifySteps(["beforeOpen"]);
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsNone(target, ".menu-two");

            beforeOpenProm.resolve();
            await nextTick();
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsOnce(target, ".menu-two");

            // Hover on THREE
            target.querySelector(".three").dispatchEvent(new MouseEvent("mouseenter"));
            await nextTick();
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsOnce(target, ".menu-three");

            // Hover on FOUR (Should not open)
            assert.containsNone(target, ".menu-four");
            target.querySelector(".four").dispatchEvent(new MouseEvent("mouseenter"));
            await nextTick();
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsOnce(target, ".menu-three");
            assert.containsNone(target, ".menu-four");

            // Click on OUTSIDE
            await click(target, "div.outside");
            assert.containsNone(target, DROPDOWN_MENU);

            // Hover on ONE, TWO, THREE
            target.querySelector(".one").dispatchEvent(new MouseEvent("mouseenter"));
            target.querySelector(".two").dispatchEvent(new MouseEvent("mouseenter"));
            target.querySelector(".three").dispatchEvent(new MouseEvent("mouseenter"));
            await nextTick();
            assert.containsNone(target, DROPDOWN_MENU);
        }
    );

    QUnit.test(
        "siblings dropdowns: when one is open, then non-sibling toggled, siblings must not be toggled on mouse-enter",
        async (assert) => {
            class Parent extends Component {
                static components = { Dropdown, DropdownGroup };
                static template = xml`
                    <div>
                        <DropdownGroup>
                            <Dropdown>
                                <button class="one">One</button>
                                <t t-set-slot="content">
                                    One Content
                                </t>
                            </Dropdown>
                        </DropdownGroup>
                        <DropdownGroup>
                            <Dropdown>
                                <button class="two">Two</button>
                                <t t-set-slot="content">
                                    Two Content
                                </t>
                            </Dropdown>
                        </DropdownGroup>
                    </div>
                `;
            }
            await mountInFixture(Parent, target);
            // Click on BAR1
            await click(target, ".two");
            assert.containsOnce(target, DROPDOWN_MENU);
            // Click on FOO
            await click(target, ".one");
            assert.containsOnce(target, DROPDOWN_MENU);
            // Hover on BAR1
            target.querySelector(".two").dispatchEvent(new MouseEvent("mouseenter"));
            await nextTick();
            assert.containsOnce(target, DROPDOWN_MENU);
            assert.containsNone(target, ".two-menu");
        }
    );

    QUnit.test("siblings dropdowns: toggler focused on mouseenter", async (assert) => {
        class Parent extends Component {
            static components = { Dropdown, DropdownGroup };
            static template = xml`
                <DropdownGroup>
                    <Dropdown>
                        <button class="one">One</button>
                        <t t-set-slot="content">
                            One Content
                        </t>
                    </Dropdown>
                    <Dropdown>
                        <button class="two">Two</button>
                        <t t-set-slot="content">
                            Two Content
                        </t>
                    </Dropdown>
                </DropdownGroup>
            `;
        }
        await mountInFixture(Parent, target);

        // Click on one
        const one = target.querySelector("button.one");
        one.focus(); // mocks a real click flow
        await click(one);
        assert.strictEqual(document.activeElement, one);
        assert.containsOnce(target, DROPDOWN_MENU);

        // Hover on two
        const two = target.querySelector("button.two");
        two.dispatchEvent(new MouseEvent("mouseenter"));
        await nextTick();
        await nextTick();
        assert.strictEqual(document.activeElement, two);
    });
});
