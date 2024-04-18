import { Component } from "@odoo/owl";

export class InternalNote extends Component {
    static template = "point_of_sale.InternalNote";
    static props = {
        notes: { type: Array, optional: true },
        class: { type: String, optional: true },
    };
    static defaultProps = {
        notes: [],
        class: "",
    };
}
