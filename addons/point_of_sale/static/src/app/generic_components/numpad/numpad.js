import { Component, useExternalListener, useState } from "@odoo/owl";
import { localization } from "@web/core/l10n/localization";

export const buttonsType = {
    type: Array,
    element: [
        {
            type: Object,
            shape: {
                value: String,
                text: { type: String, optional: true },
                class: { type: String, optional: true },
                disabled: { type: Boolean, optional: true },
                // this function has to take a string and return a string
                modifier: { type: Function, optional: true },
            },
        },
        Number,
        String,
    ],
};

export const DECIMAL = {
    get value() {
        return localization.decimalPoint;
    },
};
export const BACKSPACE = {
    value: "Backspace",
    text: "⌫",
    // TODO: handle the case where the only character left in the buffer is "-"
    modifier: (value) => value && value.slice(0, -1),
};
export const ZERO = { value: "0" };
export const DEFAULT_LAST_ROW = [
    { value: "-", text: "+/-", modifier: (value) => (value && -parseFloat(value)).toString() },
    ZERO,
    DECIMAL,
];
export const EMPTY = { value: "" };

export function getButtons(lastRow, rightColumn) {
    return [
        { value: "1" },
        { value: "2" },
        { value: "3" },
        ...(rightColumn ? [rightColumn[0]] : []),
        { value: "4" },
        { value: "5" },
        { value: "6" },
        ...(rightColumn ? [rightColumn[1]] : []),
        { value: "7" },
        { value: "8" },
        { value: "9" },
        ...(rightColumn ? [rightColumn[2]] : []),
        ...lastRow,
        ...(rightColumn ? [rightColumn[3]] : []),
    ];
}

export function enhancedButtons() {
    return getButtons(DEFAULT_LAST_ROW, [
        { value: "+10", modifier: (value) => (parseFloat(value || 0) + 10).toString() },
        { value: "+20", modifier: (value) => (parseFloat(value || 0) + 20).toString() },
        { value: "+50", modifier: (value) => (parseFloat(value || 0) + 50).toString() },
        BACKSPACE,
    ]);
}

export class Numpad extends Component {
    static template = "point_of_sale.Numpad";
    static props = {
        class: { type: String, optional: true },
        onClick: { type: Function, optional: true },
        buttons: { type: buttonsType, optional: true },
        getResetter: { type: Function, optional: true },
    };
    static defaultProps = {
        class: "numpad",
        buttons: getButtons([DECIMAL, ZERO, BACKSPACE]),
    };
    setup() {
        this.state = useState({ value: "", bufferedKeys: [] });
        this.props.getResetter?.(() => (this.state.value = ""));
        useExternalListener(window, "keydown", (event) => {
            if (["INPUT", "TEXTAREA"].includes(event.target.tagName)) {
                return;
            }
            if (document.body.classList.contains("modal-open") && !this.env.inDialog) {
                return;
            }
            const button = this.props.buttons.find((button) => button.value === event.key);
            if (!button) {
                return;
            }
            this.state.bufferedKeys.push(button);
            // Barcode Assumptions:
            const isBarcode = (keys) => keys.length > 4;
            const nonBarcodeCharacters = ["-", "Backspace", DECIMAL.value];
            const itsClearlyNotBarcode = (keys) =>
                keys.some((b) => nonBarcodeCharacters.includes(b.value));
            if (itsClearlyNotBarcode(this.state.bufferedKeys)) {
                this.onClick(...this.state.bufferedKeys);
                this.state.bufferedKeys = [];
                return;
            }
            clearTimeout(this.lastTimeout);
            this.lastTimeout = setTimeout(() => {
                if (!isBarcode(this.state.bufferedKeys)) {
                    this.onClick(...this.state.bufferedKeys);
                }
                this.state.bufferedKeys = [];
            }, 150);
        });
    }
    onClick(...buttons) {
        buttons.forEach((button) => {
            const modifier = button.modifier || ((value) => value + button.value);
            this.state.value = modifier(this.state.value);
            this.props.onClick?.({ buffer: this.state.value, key: button.value });
        });
    }
}
