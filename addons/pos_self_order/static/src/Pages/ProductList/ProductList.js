/** @odoo-module */

import { Component, onMounted, useEffect, useRef, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/SelfOrderService";
import { useAutofocus, useChildRef } from "@web/core/utils/hooks";
import { NavBar } from "@pos_self_order/Components/NavBar/NavBar";
import { ProductCard } from "@pos_self_order/Components/ProductCard/ProductCard";
import { fuzzyLookup } from "@web/core/utils/search";
import { useScrollDirection } from "@pos_self_order/Hooks/useScrollDirection";
import { effect } from "@point_of_sale/utils";
export class ProductList extends Component {
    static template = "pos_self_order.ProductList";
    static props = [];
    static components = {
        NavBar,
        ProductCard,
    };
    setup() {
        this.privateState = useState({
            selectedTag: "",
            searchIsFocused: false,
            searchInput: "",
            navbarIsShown: true,
            scrollingDown: false,
            scrolling: false,
        });
        this.selfOrder = useSelfOrder();
        useAutofocus({ refName: "searchInput", mobile: true });
        this.productsList = useRef("productsList");

        // reference to the last visited product
        // (used to scroll back to it when the user comes back from the product page)
        this.currentProductCard = useChildRef();

        // object with references to each tag heading
        this.productGroup = Object.fromEntries(
            Array.from(this.selfOrder.tagList).map((tag) => {
                return [tag, useRef(`productsWithTag_${tag}`)];
            })
        );
        this.tagButtons = Object.fromEntries(
            Array.from(this.selfOrder.tagList).map((tag) => {
                return [tag, useRef(`tag_${tag}`)];
            })
        );
        this.tagList = useRef("tagList");
        this.header = useRef("header");
        this.productPage = useRef("productPage");
        this.main = useRef("main");
        this.orderButton = useRef("orderButton");

        // this is used to hide the navbar when the user is scrolling down
        this.scroll = useScrollDirection(this.productsList);
        effect(
            (scroll) => {
                console.log(scroll.down);
                if (this.productPage.el) {
                    this.toggleNavbar(scroll.down);
                }
            },
            [this.scroll]
        );
        onMounted(() => {
            // TODO: replace this logic with dvh once it is supported
            this.main.el.style.height = `${window.innerHeight}px`;

            this.headerHeight = this.header.el.offsetHeight;
            this.navbarHeight = this.header.el.querySelector("nav").offsetHeight;

            this.productPage.el.style.height = `${
                window.innerHeight - (this.orderButton?.el?.offsetHeight ?? 0)
            }px`;

            // The productList has to have a height; otherwise overflow-auto won't scroll
            this.productsList.el.style.height = `${
                window.innerHeight - this.headerHeight - (this.orderButton?.el?.offsetHeight ?? 0)
            }px`;

            // if the user is coming from the product page
            // we scroll back to the product card that he was looking at before
            if (this.selfOrder.currentProduct) {
                this.scrollTo(this.currentProductCard, { behavior: "instant" });
            }
        });
        // this IntersectionObserver is used to highlight the tag (in the header)
        // of the category that is currently visible in the viewport
        useEffect(
            (searchIsFocused) => {
                if (searchIsFocused) {
                    return;
                }
                const OBSERVING_WINDOW_HEIGHT = 5;
                const observer = new IntersectionObserver(
                    (entries) => {
                        const entry = entries.filter((entry) => entry.isIntersecting)?.[0];
                        if (entry) {
                            this.privateState.selectedTag =
                                entry.target.querySelector("h3").textContent;
                            // we scroll the tag list horizontally so that the selected tag is in the middle of the screen
                            this.tagList?.el?.scroll({
                                top: 0,
                                left:
                                    this.tagButtons[this.privateState.selectedTag].el.offsetLeft -
                                    window.innerWidth / 2,
                                behavior: "smooth",
                            });
                        }
                    },
                    {
                        root: this.productsList.el,
                        rootMargin: `0px 0px -${
                            this.productsList.el.offsetHeight -
                            (parseInt(this.productsList.el?.style?.paddingBottom) || 0) -
                            OBSERVING_WINDOW_HEIGHT
                        }px 0px`,
                    }
                );
                Object.keys(this.productGroup).forEach((tag) => {
                    observer.observe(this.productGroup[tag]?.el);
                });
                return () => {
                    observer.disconnect();
                };
            },
            () => [this.privateState.searchIsFocused]
        );
    }
    /**
     * This function hides or shows the navbar by sliding the whole productPage up or down
     * @param {boolean} hide - true if the navbar should be hidden, false otherwise
     */
    toggleNavbar(hide) {
        this.privateState.navbarIsShown = !this.privateState.navbarIsShown;

        const defaultHeight =
            window.innerHeight - this.headerHeight - (this.orderButton?.el?.offsetHeight ?? 0);
        const elongate = hide
            ? [
                  { height: `${defaultHeight}px` },
                  { height: `${defaultHeight + this.navbarHeight}px` },
              ]
            : [
                  { height: `${defaultHeight + this.navbarHeight}px` },
                  { height: `${defaultHeight}px` },
              ];
        const slide = hide
            ? [{ top: "0px" }, { top: `-${this.navbarHeight}px` }]
            : [{ top: `-${this.navbarHeight}px` }, { top: "0px" }];

        this.productPage.el.animate(slide, {
            duration: 200,
            fill: "forwards",
        });
        this.productsList.el.animate(elongate, {
            duration: 200,
            fill: "forwards",
        });
    }

    scrollToTop() {
        this.productsList?.el?.scroll({
            top: 0,
            left: 0,
            behavior: "smooth",
        });
    }
    /**
     * This function scrolls the productsList to the ref passed as argument,
     *            it takes into account the height of the header
     * @param {Object} ref - the ref to scroll to
     */
    scrollTo(ref, { behavior = "smooth" } = {}) {
        const y = ref?.el.offsetTop;
        // the intersection observer will detect on which product category we are and
        // it is possible that after scrolling we are a couple of pixels short of the desired category
        // so it actually sees the previous category. To avoid this we add a small correction
        const SCROLL_CORRECTION = 4;
        const scrollOffset = this.headerHeight - SCROLL_CORRECTION;
        this.productsList?.el?.scroll({
            top: y - scrollOffset,
            behavior,
        });
    }
    /**
     * This function returns the list of products that should be displayed;
     *             it filters the products based on the search input
     * @returns {Object} the list of products that should be displayed
     */
    filteredProducts() {
        if (!this.privateState.searchInput) {
            return this.selfOrder.products;
        }
        return fuzzyLookup(
            this.privateState.searchInput,
            this.selfOrder.products,
            (product) => product.name + product.description_sale
        );
    }
    /**
     * This function is called when a tag is clicked; it selects the chosen tag and deselects all the other tags
     * @param {string} tag_name
     */
    selectTag(tag_name) {
        if (this.privateState.selectedTag === tag_name) {
            this.privateState.selectedTag = "";
            this.scrollToTop();
            return;
        }
        // When the user clicks on a tag, we scroll to the part of the page
        // where the products with that tag are displayed.
        // after the scrolling is done, the intersection observer will
        // automatically set the privateState.selectedTag to the tag_name
        this.scrollTo(this.productGroup[tag_name]);
    }
    /**
     * This function is called when the search button is clicked.
     * It sets the state so the search input is focused.
     * It also deselects all the selected tags
     */
    focusSearch() {
        this.privateState.searchIsFocused = true;
        if (this.privateState.navbarIsShown) {
            this.toggleNavbar(true);
        }
        this.scrollToTop();
    }
    /**
     * This function is called when the search input 'x' button is clicked
     */
    closeSearch() {
        this.privateState.searchIsFocused = false;
        this.privateState.searchInput = "";
    }
}
