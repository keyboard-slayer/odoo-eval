import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/self_order_service";
import { cookie } from "@web/core/browser/cookie";
import { useService } from "@web/core/utils/hooks";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { rpc } from "@web/core/network/rpc";
import { OutOfPaperPopup } from "@pos_self_order/app/components/out_of_paper_popup/out_of_paper_popup";

export class ConfirmationPage extends Component {
    static template = "pos_self_order.ConfirmationPage";
    static props = ["orderAccessToken", "screenMode"];

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        this.printer = useService("printer");
        this.dialog = useService("dialog");
        this.confirmedOrder = {};
        this.changeToDisplay = [];
        this.state = useState({
            onReload: false,
            payment: this.props.screenMode === "pay",
        });

        onMounted(() => {
            if (this.selfOrder.config.self_ordering_mode === "kiosk") {
                setTimeout(() => {
                    this.setDefautLanguage();
                }, 5000);

                setTimeout(async () => {
                    try {
                        await this.printer.print(OrderReceipt, {
                            data: this.selfOrder.export_for_printing(this.confirmedOrder),
                            formatCurrency: this.selfOrder.formatMonetary,
                        });
                        if (!this.selfOrder.has_paper) {
                            this.updateHasPaper(true);
                        }
                    } catch (e) {
                        if (e.errorCode === "EPTR_REC_EMPTY") {
                            this.dialog.add(OutOfPaperPopup, {
                                title: `No more paper in the printer, please remember your order number: '${this.confirmedOrder.trackingNumber}'.`,
                                close: () => {
                                    this.router.navigate("default");
                                },
                            });
                            this.updateHasPaper(false);
                        } else {
                            console.error(e);
                        }
                    }
                }, 500);
                this.defaultTimeout = setTimeout(() => {
                    this.router.navigate("default");
                }, 30000);
            }
        });
        onWillUnmount(() => {
            clearTimeout(this.defaultTimeout);
        });

        this.initOrder();
    }

    async initOrder() {
        const order = this.selfOrder.orders.find(
            (o) => o.access_token === this.props.orderAccessToken
        );

        const paymentMethods = this.selfOrder.pos_payment_methods.filter(
            (p) => p.is_online_payment
        );

        if (
            !order ||
            (paymentMethods.length > 0 &&
                this.selfOrder.config.self_ordering_mode === "mobile" &&
                this.selfOrder.config.self_ordering_pay_after === "each" &&
                order.state !== "paid")
        ) {
            this.router.navigate("default");
            return;
        }

        this.confirmedOrder = order;
    }

    backToHome() {
        if (!this.setDefautLanguage()) {
            this.router.navigate("default");
        }
    }

    async updateHasPaper(state) {
        await rpc("/pos-self-order/change-printer-status", {
            access_token: this.selfOrder.access_token,
            has_paper: state,
        });
        this.selfOrder.has_paper = state;
    }

    setDefautLanguage() {
        const defaultLanguage = this.selfOrder.config.self_ordering_default_language_id;

        if (
            this.selfOrder.currentLanguage.code !== defaultLanguage.code &&
            !this.state.onReload &&
            this.selfOrder.config.self_ordering_mode === "kiosk"
        ) {
            cookie.set("frontend_lang", defaultLanguage.code);
            window.location.reload();
            this.state.onReload = true;
            return true;
        }

        return this.state.onReload;
    }
}
