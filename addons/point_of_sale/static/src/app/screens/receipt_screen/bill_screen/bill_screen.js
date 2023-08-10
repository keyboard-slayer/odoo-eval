/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { registry } from "@web/core/registry";

export class BillScreen extends ReceiptScreen {
    static template = "point_of_sale.BillScreen";
    confirm() {
        this.props.resolve({ confirmed: true, payload: null });
        this.pos.closeTempScreen();
    }
    whenClosing() {
        this.confirm();
    }
    /**
     * @override
     */
    async printReceipt() {
        await super.printReceipt();
        this.currentOrder._printed = false;
    }
}

registry.category("pos_screens").add("BillScreen", BillScreen);
