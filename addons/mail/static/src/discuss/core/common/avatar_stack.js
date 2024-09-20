import { Component } from "@odoo/owl";

export class AvatarStack extends Component {
    static template = "mail.AvatarStack";
    static props = ["personas", "max?", "total?", "size?"];
    static defaultProps = {
        max: 4,
        size: 14,
    };

    getStyle(index) {
        let style = `width: ${this.props.size}px; height: ${this.props.size}px;`;
        if (index === 0) {
            return style;
        }
        // Compute cumulative offset,
        style += `margin-left: -${this.props.size / 3}px`;
        return style;
    }

    get total() {
        return this.props.total ?? this.props.personas.length;
    }
}
