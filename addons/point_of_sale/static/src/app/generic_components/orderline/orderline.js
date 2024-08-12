import { Component } from "@odoo/owl";
import { InternalNote } from "@point_of_sale/app/generic_components/internal_note/internal_note";

export class Orderline extends Component {
    static components = { InternalNote };
    static template = "point_of_sale.Orderline";
    static props = {
        class: { type: Object, optional: true },
        line: {
            type: Object,
            shape: {
                isSelected: { type: Boolean, optional: true },
                productName: String,
                price: String,
                qty: String,
                unit: { type: String, optional: true },
                unitPrice: String,
                discount: { type: String, optional: true },
                comboParent: { type: String, optional: true },
                oldUnitPrice: { type: String, optional: true },
                customerNote: { type: String, optional: true },
                internalNote: { type: Array, optional: true },
                note_ids: { type: Array, optional: true },
                imageSrc: { type: String, optional: true },
                packLotLines: { type: Array, optional: true },
                price_without_discount: { type: String, optional: true },
                taxGroupLabels: { type: String, optional: true },
            },
        },
        showTaxGroupLabels: { type: Boolean, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = {
        class: {},
        showTaxGroupLabels: false,
    };
}
