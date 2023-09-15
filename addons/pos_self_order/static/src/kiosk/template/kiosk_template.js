/** @odoo-module */

import { Component, markup, onMounted } from "@odoo/owl";
import { useselfOrder } from "@pos_self_order/kiosk/self_order_kiosk_service";
import { useService } from "@web/core/utils/hooks";
import { escape } from "@web/core/utils/strings";

export class KioskTemplate extends Component {
    static template = "pos_self_order.KioskTemplate";
    static props = ["hasFixedContent", "slots"];

    setup() {
        this.selfOrder = useselfOrder();
        this.selfOrder.isSession();
        this.router = useService("router");
        this.idleTimer = null;

        onMounted(() => {
            const style = document.createElement("style");
            const color = escape(this.selfOrder.color);
            style.innerHTML = markup(`
            body {
                --companyColor: ${color};
            }`);

            document.getElementsByTagName("head")[0].appendChild(style);
            window.addEventListener("touchstart", () => this.idleDetector());
            window.addEventListener("mousedown", () => this.idleDetector());
            window.addEventListener("click", () => this.idleDetector());
            window.addEventListener("load", () => this.idleDetector());

            // disable right click, on your mobile (tactil kiosk),
            // you can right-click while holding down the key
            document.addEventListener("contextmenu", (event) => {
                event.preventDefault();
            });
        });
    }

    idleDetector() {
        clearTimeout(this.idleTimer);
        this.idleTimer = setTimeout(() => this.router.navigate("default"), 3 * 60 * 1000); // 5 minutes
    }

    get showShadow() {
        return this.router.activeSlot === "default" ? false : true;
    }
}
