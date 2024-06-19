import PublicWidget from "@web/legacy/js/public/public_widget";

export const CapsLockWarningWidget = PublicWidget.Widget.extend({
    selector: "[data-widget='caps-lock-check']",
    events: {
        "keydown .password-input": "_onKeyDownEvent",
    },

    /**
     * @override
     */
    start() {
        this.capsLockWarning = document.querySelector("#caps_lock_warning");
        return this._super.apply(this, arguments);
    },

    /**
     * Capture keydown events to detect the CAPS LOCK state and toggle the
     * CAPS LOCK warning accordingly
     *
     * @private
     * @param {KeyboardEvent} ev
     */
    _onKeyDownEvent(ev) {
        // Check if Caps Lock is active.
        const isCapsLockActive = ev.originalEvent.getModifierState?.("CapsLock");

        // `false` value REMOVES the `invisible` class while `true` ADDS it.
        const toggleVisibility = ev.key === "CapsLock" ? isCapsLockActive : !isCapsLockActive;

        // Toggle "invisible" class to show/hide the warning
        this.capsLockWarning.classList.toggle("invisible", toggleVisibility);
    },
});

PublicWidget.registry.CapsLockWarningWidget = CapsLockWarningWidget;
