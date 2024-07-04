odoo.define("website_payment.wysiwyg", function (require) {
    "use strict";

const Wysiwyg = require("web_editor.wysiwyg");

Wysiwyg.include({
    /**
     * @override
     */
    removeLink() {
        const RequiredButtons = ["s_website_form_send", "s_donation_donate_btn"];
        if (RequiredButtons.some(className => this.lastElement.classList.contains(className))) {
            return;
        }
        this._super(...arguments);
    },
});
});
