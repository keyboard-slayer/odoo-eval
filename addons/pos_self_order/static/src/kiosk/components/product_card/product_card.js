/** @odoo-module */

import { Component, useRef } from "@odoo/owl";
import { useselfOrder } from "@pos_self_order/kiosk/self_order_kiosk_service";
import { useService, useForwardRefToParent } from "@web/core/utils/hooks";
import { Line } from "@pos_self_order/common/models/line";

export class ProductCard extends Component {
    static template = "pos_self_order.ProductCard";
    static props = ["product", "currentProductCard?", "animation?", "animationDelay?"];

    selfRef = useRef("selfProductCard");
    currentProductCardRef = useRef("currentProductCard");

    setup() {
        this.selfOrder = useselfOrder();
        this.router = useService("router");

        useForwardRefToParent("currentProductCard");
    }

    flyToCart() {
        const productCardEl = this.selfRef.el;
        if (!productCardEl) return;

        const cartButton = document.querySelector(".cart");
        if (!cartButton || window.getComputedStyle(cartButton).display === 'none') {
            return;
        }

        const clonedCard = productCardEl.cloneNode(true);
        const cardRect = productCardEl.getBoundingClientRect();
        const cartRect = cartButton.getBoundingClientRect();

        clonedCard.classList.remove('o_kiosk_product_card_animated');
        clonedCard.style.position = "absolute";
        clonedCard.style.top = `${cardRect.top}px`;
        clonedCard.style.left = `${cardRect.left}px`;
        clonedCard.style.width = `${cardRect.width}px`;
        clonedCard.style.height = `${cardRect.height}px`;
        clonedCard.style.opacity = ".85";
        clonedCard.style.transition = "top 1s cubic-bezier(0.95, 0.1, 0.25, 0.95), left 1s cubic-bezier(0.95, 0.1, 0.25, 0.95), width 1s cubic-bezier(0.95, 0.1, 0.25, 0.95), height 1s cubic-bezier(0.95, 0.1, 0.25, 0.95), opacity 0.6s 0.2s ease-in-out";
        

        document.body.appendChild(clonedCard);

        requestAnimationFrame(() => {
            clonedCard.style.top = `${cartRect.top}px`;
            clonedCard.style.left = `${cartRect.left}px`;
            clonedCard.style.width = `${cardRect.width * 0.80}px`;
            clonedCard.style.height = `${cardRect.height * 0.80}px`;
            clonedCard.style.opacity = "0"; // Fading out the card
        });

        clonedCard.addEventListener('transitionend', () => {
            clonedCard.remove();
        });
    }
    
    async selectProduct() {
        const product = this.props.product;

        if (product.isCombo) {
            this.router.navigate("combo", { id: product.id });
        } else if (product.attributes.length > 0) {
            this.router.navigate("product", { id: product.id });
        } else {
            this.flyToCart();
            const isProductInCart = this.selfOrder.currentOrder.lines.find(
                (line) => line.product_id === product.id
            );

            if (isProductInCart) {
                isProductInCart.qty++;
            } else {                
                const lines = this.selfOrder.currentOrder.lines;

                lines.push(
                    new Line({
                        id: null,
                        uuid: null,
                        qty: 1,
                        product_id: product.id,
                        full_product_name: product.name,
                    })
                );
            }
            await this.selfOrder.getPricesFromServer();
        }
    }
}
