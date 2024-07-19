import { useEffect, useRef, Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { router, stateToUrl } from "@web/core/browser/router";
import { useService } from "./hooks";

const EXCLUDED_TAGS = ["A", "IMG"];
class OptionsMenuPopover extends Component {
    static components = {
        DropdownItem,
    };
    static template = xml`
        <t t-foreach="props.options" t-as="option" t-key="option.description">
            <div t-if="option.separator" role="separator" class="dropdown-divider"></div>
            <DropdownItem t-else="" onSelected="() => this.onSelected(option.callback)"><i t-attf-class="fa me-2 {{option.icon}}"/><t t-out="option.description"/></DropdownItem>
        </t>
    `;
    static props = {
        close: Function,
        options: Object,
    };

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    onSelected(callback) {
        callback();
        this.props.close();
    }
}

export function useMiddleClick({ refName, clickParams, selector, contextMenuOptions = [] }) {
    const ref = useRef(refName || "middleclick");
    const popoverService = useService("popover");
    let _onCtrlClick;
    if (clickParams) {
        if (clickParams.onCtrlClick) {
            _onCtrlClick = clickParams.onCtrlClick;
        } else if (clickParams.record) {
            _onCtrlClick = (ev) => {
                const actionStack = [
                    ...router.current.actionStack,
                    {
                        action: clickParams.record.action,
                        model: clickParams.record.resModel,
                        resId: clickParams.record.resId,
                    },
                ];
                const href = stateToUrl({
                    actionStack,
                });
                ev?.preventDefault();
                ev?.stopPropagation();
                window.open(href);
            };
        }
    }
    const handleClick = (ev) => {
        if (
            !ev.target.classList.contains("middle_clickable") &&
            EXCLUDED_TAGS.find((tag) => ev.target.closest(`${tag}`))
        ) {
            // keep the default browser behavior if the click on the element is not explicitly handled by the hook
            return;
        }
        if ((_onCtrlClick && ev.ctrlKey && ev.button === 0) || ev.button === 1) {
            _onCtrlClick(ev);
        } else if (!ev.ctrlKey && ev.button === 2) {
            ev.preventDefault();
            displayOptionMenu(ev.target);
            return false;
        }
    };
    let touchTimeout;
    let _preventTouchEnd = false;
    const displayOptionMenu = (target) => {
        const options = [...contextMenuOptions];
        const displayOpenOption = _onCtrlClick || clickParams.displayOpenOption;
        if (displayOpenOption) {
            options.unshift({
                icon: "fa-external-link",
                callback: () => {
                    if (clickParams.isRouterHandled) {
                        router.enableOpenNewWindow();
                        ref.el.click();
                        router.disableOpenNewWindow();
                    } else {
                        _onCtrlClick();
                    }
                },
                description: _t("Open in new tab"),
            });
        }
        if (!options.length) {
            return;
        }
        popoverService.add(
            target,
            OptionsMenuPopover,
            {
                options,
            },
            {
                arrow: false,
                role: "menu",
                popoverClass: "o-dropdown--menu dropdown-menu mx-0",
            }
        );
    };
    const styleControlPressed = (ev) => {
        if (ev.key === "Control") {
            document.body.classList.add("ctrl_key_pressed");
            if (clickParams.isRouterHandled) {
                router.enableOpenNewWindow();
            }
        }
    };
    const styleControlUp = (ev) => {
        if (ev.key === "Control") {
            document.body.classList.remove("ctrl_key_pressed");
            if (clickParams.isRouterHandled) {
                router.disableOpenNewWindow();
            }
        }
    };
    const onTouchStart = (ev) => {
        touchTimeout = setTimeout(() => {
            _preventTouchEnd = true;
            displayOptionMenu(ev.target);
        }, 500);
    };

    const onTouchCancel = (ev) => {
        if (_preventTouchEnd) {
            // this prevents the browser context menu to appear, or to trigger a click
            // under the element, to use the popover sould be used instead
            _preventTouchEnd = false;
            ev.preventDefault();
        }
        clearTimeout(touchTimeout);
    };
    useEffect(
        () => {
            if (ref.el) {
                const els = selector ? ref.el.querySelectorAll(selector) : [ref.el];
                els.forEach((el) => {
                    el.classList.add("middle_clickable");
                    if (clickParams.record) {
                        el.classList.add("middle_clickable_record");
                    }
                    el.addEventListener("click", handleClick, { capture: true });
                    el.addEventListener("contextmenu", handleClick, { capture: true });
                    el.addEventListener("touchstart", onTouchStart, { capture: true });
                    el.addEventListener("touchend", onTouchCancel, { capture: true });
                    //el.addEventListener("touchmove", onTouchCancel, { capture: true });
                });
                window.addEventListener("keydown", styleControlPressed);
                window.addEventListener("keyup", styleControlUp);
                return () => {
                    els.forEach((el) => {
                        el.removeEventListener("click", handleClick);
                    });
                    window.removeEventListener("keydown", styleControlPressed);
                    window.removeEventListener("keyup", styleControlUp);
                };
            }
        },
        () => [ref.el]
    );
}
