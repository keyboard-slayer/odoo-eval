/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

import { CheckIdentityForm } from "@web/core/check_identity/check_identity_service";

import { startAuthentication } from "../../lib/simplewebauthn.js";

patch(CheckIdentityForm.prototype, {
    async onClick(ev) {
        const form = ev.target.closest('form');
        if (form.querySelector('input[name="type"]').value === 'webauthn'){
            const serverOptions = await rpc("/auth/passkey/start-auth");
            const auth = await startAuthentication(serverOptions).catch(e => console.log(e));
            if(!auth) return false;
            form.querySelector('input[name="webauthn_response"]').value = JSON.stringify(auth);
        }
        super.onClick(ev);
    },
});
