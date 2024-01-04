/** @odoo-module **/
import { useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { throttleForAnimation, debounce } from "@web/core/utils/timing";
import { scrollTo } from "@web/core/utils/scrolling";

/**
 * @typedef {Object} NavigationOptions
 * @property {keyHandlerCallback} onArrowUp
 * @property {keyHandlerCallback} onArrowDown
 * @property {keyHandlerCallback} onArrowLeft
 * @property {keyHandlerCallback} onArrowRight
 * @property {keyHandlerCallback} onHome
 * @property {keyHandlerCallback} onEnd
 * @property {keyHandlerCallback} onTab
 * @property {keyHandlerCallback} onShiftTab
 * @property {keyHandlerCallback} onEnter
 * @property {Function} onEscape
 * @property {Function} onOpen
 * @property {Function} onMouseEnter
 * @property {Boolean} [virtualFocus=false] - If true, items are only visually
 * focused so the actual focus can be kept on another input.
 * @property {string} [itemsSelector=":scope .o-navigable"] - The selector used to get the list
 * of navigable elements.
 * @property {Function} focusInitialElementOnDisabled
 */

/**
 * Callback used to override the behaviour of a specific
 * key input.
 *
 * @callback keyHandlerCallback
 * @param {number} index                Current index.
 * @param {Array<NavigationItem>} items List of all navigation items.
 */

const ACTIVE_ELEMENT_CLASS = "focus";
const throttledElementFocus = throttleForAnimation((el) => el?.focus());

function focusElement(el) {
    throttledElementFocus.cancel();
    throttledElementFocus(el);
}

class NavigationItem {
    constructor({ index, el, setActiveItem, options }) {
        this.index = index;
        this.options = options;
        this.setActiveItem = setActiveItem;

        this.el = el;
        if (options.shouldFocusChildInput) {
            const subInput = el.querySelector(":scope input, :scope button, :scope textarea");
            this.target = subInput || el;
        } else {
            this.target = el;
        }
    }

    addListeners() {
        this.target.addEventListener("focus", this.focus);
        this.target.addEventListener("mouseenter", this.onMouseEnter);
    }

    removeListeners() {
        this.target.removeEventListener("focus", this.focus);
        this.target.removeEventListener("mouseenter", this.onMouseEnter);
    }

    select() {
        this.focus();
        this.target.click();
    }

    focus(event) {
        scrollTo(this.target);
        this.setActiveItem(this.index, this.target);
        this.target.classList.add(ACTIVE_ELEMENT_CLASS);

        if (!event && !this.options.virtualFocus) {
            focusElement(this.target);
        }
    }

    defocus() {
        this.target.classList.remove(ACTIVE_ELEMENT_CLASS);
    }

    onMouseEnter() {
        this.focus();
        if (this.options.onMouseEnter) {
            this.options.onMouseEnter(this);
        }
    }
}

class Navigator {
    /**
     * @param {*} containerRef
     * @param {NavigationOptions} options
     */
    constructor(containerRef, options, hotkeyService) {
        this.enabled = false;
        this.containerRef = containerRef;

        const focusAt = (increment) => {
            const isFocused = [...this.activeItems].some((el) => el.isConnected);
            const index = this.currentActiveIndex + increment;
            if (isFocused && index >= 0) {
                return this.items[index % this.items.length]?.focus();
            } else if (!isFocused && increment >= 0) {
                return this.items[0]?.focus();
            } else {
                return this.items.at(-1)?.focus();
            }
        };

        this.options = {
            shouldFocusChildInput: true,
            virtualFocus: false,
            itemsSelector: ":scope .o-navigable",
            focusInitialElementOnDisabled: () => true,

            onHome: (index, items) => items[0]?.focus(),
            onEnd: (index, items) => items.at(-1)?.focus(),
            onTab: () => focusAt(+1),
            onShiftTab: () => focusAt(-1),
            onArrowDown: () => focusAt(+1),
            onArrowUp: () => focusAt(-1),
            onArrowLeft: () => {},
            onArrowRight: () => {},
            onEnter: (index, items) => items[index]?.select(),

            ...options,
        };

        /**@type {Array<NavigationItem>} */
        this.items = [];
        /**@type {Set<HTMLElement>} */
        this.activeItems = new Set();
        this.currentActiveIndex = -1;
        this.initialFocusElement = undefined;
        this.debouncedUpdate = debounce(() => this.update(), 100);

        this.hotkeyRemoves = [];
        this.hotkeyService = hotkeyService;
        this.BYPASSED_HOTKEYS = ["arrowup", "arrowdown", "enter"];
        this.hotkeyCallbacks = {
            home: () => this.options.onHome(this.currentActiveIndex, this.items),
            end: () => this.options.onEnd(this.currentActiveIndex, this.items),
            tab: () => this.options.onTab(this.currentActiveIndex, this.items),
            "shift+tab": () => this.options.onShiftTab(this.currentActiveIndex, this.items),
            arrowdown: () => this.options.onArrowDown(this.currentActiveIndex, this.items),
            arrowup: () => this.options.onArrowUp(this.currentActiveIndex, this.items),
            arrowleft: () => this.options.onArrowLeft(this.currentActiveIndex, this.items),
            arrowright: () => this.options.onArrowRight(this.currentActiveIndex, this.items),
            escape: () => this.options.onEscape(this.currentActiveIndex, this.items),
            enter: () => this.options.onEnter(this.currentActiveIndex, this.items),
        };
    }

    selectElement(index, overrideOption) {
        if (overrideOption) {
            overrideOption(this.currentActiveIndex, this.items);
        } else if (index !== undefined && index >= 0 && index < this.items.length) {
            this.items[index].focus();
        }
    }

    enable() {
        if (!this.containerRef.el || this.targetObserver) {
            return;
        }

        this.enabled = true;

        for (const [hotkey, callback] of Object.entries(this.hotkeyCallbacks)) {
            this.hotkeyRemoves.push(
                this.hotkeyService.add(hotkey, callback, {
                    allowRepeat: true,
                    bypassEditableProtection: this.BYPASSED_HOTKEYS.includes(hotkey),
                })
            );
        }

        this.targetObserver = new MutationObserver(() => this.debouncedUpdate());
        this.targetObserver.observe(this.containerRef.el, {
            childList: true,
            subtree: true,
        });

        this.resizeObserver = new ResizeObserver(() => this.debouncedUpdate());
        this.resizeObserver.observe(this.containerRef.el);

        this.initialFocusElement = document.activeElement;
        this.currentActiveIndex = -1;
        this.update();

        if (this.options.onOpen) {
            this.options.onOpen(this.items);
        } else if (this.items.length > 0) {
            this.items[0]?.focus();
        }
    }

    disable() {
        if (!this.enabled) {
            return;
        }

        this.enabled = false;

        if (this.targetObserver) {
            this.targetObserver.disconnect();
            this.targetObserver = undefined;
        }

        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = undefined;
        }

        this.clearItems();
        for (const removeHotkey of this.hotkeyRemoves) {
            removeHotkey();
        }
        this.hotkeyRemoves = [];

        if (this.options.focusInitialElementOnDisabled()) {
            focusElement(this.initialFocusElement);
        }
    }

    update() {
        if (!this.containerRef.el) {
            return;
        }
        this.clearItems();

        const elements = [...this.containerRef.el.querySelectorAll(this.options.itemsSelector)];
        this.items = elements.map((el, index) => {
            return new NavigationItem({
                index,
                el,
                options: this.options,
                setActiveItem: (index, el) => this.setActiveItem(index, el),
            });
        });
    }

    setActiveItem(index, target) {
        this.activeItems.forEach((el) => {
            el.classList.remove(ACTIVE_ELEMENT_CLASS);
        });
        this.activeItems.clear();
        this.activeItems.add(target);
        this.currentActiveIndex = index;
    }

    clearItems() {
        for (const item of this.items) {
            item.removeListeners();
        }
        this.items = [];
    }
}

/**
 * @param {*} containerRef
 * @param {NavigationOptions} options
 */
export function useNavigation(containerRef, options = {}) {
    const hotkeyService = useService("hotkey");
    const navigator = new Navigator(containerRef, options, hotkeyService);

    useEffect(
        (container) => {
            if (container) {
                navigator.enable();
            } else if (navigator) {
                navigator.disable();
            }
        },
        () => [containerRef.el]
    );

    return {
        enable: () => navigator.enable(),
        disable: () => navigator.disable(),
    };
}
