import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

export class OrderlineNoteButton extends Component {
    static template = "point_of_sale.OrderlineNoteButton";
    static props = {
        icon: { type: String, optional: true },
        label: { type: String, optional: true },
        getter: { type: Function, optional: true },
        setter: { type: Function, optional: true },
        class: { type: String, optional: true },
    };
    static defaultProps = {
        label: _t("Customer Note"),
        getter: (orderline) => orderline.get_customer_note(),
        setter: (orderline, note) => orderline.set_customer_note(note),
        class: "",
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
    }
    async onClick() {
        const selectedOrderline = this.pos.get_order().get_selected_orderline();
        const orderlineNotes = this.props.getter(selectedOrderline);
        const selectedNote = orderlineNotes
            ? orderlineNotes.map((note) => note.name).join("\n")
            : "";
        const notes = this.pos.models["pos.note"].filter((note) => typeof note.id !== "string");
        let buttons;
        if (this._isInternalNote()) {
            buttons = notes.map((note) => ({
                label: note.name,
                class: note.color ? `o_colorlist_item_color_${note.color}` : "",
                isSelected: selectedNote?.includes(note.name), // Check if the note is already selected
                isActive: note.is_displayed,
            }));
        } else {
            buttons = [];
        }

        buttons = buttons.filter((button) => button.isActive || button.isSelected);
        const oldNote = selectedOrderline.note_ids.map((note) => note.name).join("\n");
        const payload = await makeAwaitable(this.dialog, TextInputPopup, {
            title: _t("Add %s", this.props.label),
            buttons,
            rows: 4,
            startingValue: selectedNote,
        });

        var quantity_with_note = 0;
        const changes = this.pos.getOrderChanges();
        for (const key in changes.orderlines) {
            if (changes.orderlines[key].uuid == selectedOrderline.uuid) {
                quantity_with_note = changes.orderlines[key].quantity;
                break;
            }
        }
        const saved_quantity = selectedOrderline.qty - quantity_with_note;
        if (saved_quantity > 0 && quantity_with_note > 0) {
            await this.pos.addLineToCurrentOrder({
                product_id: selectedOrderline.product_id,
                qty: quantity_with_note,
                note: payload,
            });
            selectedOrderline.qty = saved_quantity;
        } else {
            this.props.setter(selectedOrderline, payload);
        }

        return { confirmed: typeof payload === "string", inputNote: payload, oldNote };
    }
    _isInternalNote() {
        return this.props.label == _t("Internal Note");
    }
}
