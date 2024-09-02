/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { escape } from "@web/core/utils/strings";
import { registry } from "@web/core/registry";
import { pick } from "@web/core/utils/objects";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { Component, markup, useState } from "@odoo/owl";

const waitTime = 60000;

class NemhandelSettingsButtons extends Component {
    static props = {
        ...standardWidgetProps,
    };
    static template = "l10n_dk_nemhandel.ActionButtons";

    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            isSmsButtonDisabled: false,
        });
    }

    get proxyState() {
        return this.props.record.data.l10n_dk_nemhandel_proxy_state;
    }

    get ediMode() {
        return this.props.record.data.l10n_dk_nemhandel_edi_mode;
    }

    get modeConstraint() {
        return this.props.record.data.l10n_dk_nemhandel_mode_constraint;
    }

    get createUserButtonLabel() {
        const modes = {
            demo: _t("Validate registration (Demo)"),
            test: _t("Validate registration (Test)"),
            prod: _t("Validate registration"),
        }
        return modes[this.ediMode] || _t("Validate registration");
    }

    get deregisterUserButtonLabel() {
        const modes = {
            demo: _t("Switch to Live"),
        }
        return this.modeConstraint !== "demo" && modes[this.ediMode] || _t("Deregister from Nemhandel");
    }

    async _callConfigMethod(methodName, save = false) {
        if (save) {
            await this._save();
        }
        this.env.onClickViewButton({
            clickParams: {
                name: methodName,
                type: "object",
                noSaveDialog: true,
            },
            getResParams: () =>
                pick(this.env.model.root, "context", "evalContext", "resModel", "resId", "resIds"),
        });
    }

    async _save () {
        this.env.model.root.save({ reload: false });
    }

    showConfirmation(warning, methodName) {
        const message = _t(warning);
        const confirmMessage = _t("You will not be able to send or receive Nemhandel documents in Odoo anymore. Are you sure you want to proceed?");
        this.dialogService.add(ConfirmationDialog, {
            body: markup(
                `<div class="text-danger">${escape(message)}</div>
                <div class="text-danger">${escape(confirmMessage)}</div>`
            ),
            confirm: async () => {
                await this._callConfigMethod(methodName);
            },
            cancel: () => { },
        });
    }

    deregister() {
        if (this.ediMode === 'demo') {
            this._callConfigMethod("button_l10n_dk_nemhandel_deregister_participant");
        } else {
            this.showConfirmation(
                "This will delete your Nemhandel registration.",
                "button_l10n_dk_nemhandel_deregister_participant"
            )
        }
    }

    async updateDetails() {
        // avoid making users click save on the settings
        // and then clicking the update button
        // changes on both the client side and the iap side need to be saved within one method
        await this._callConfigMethod("button_update_l10n_dk_nemhandel_user_data", true);
        this.notification.add(
            _t("Contact details were updated."),
            { type: "success" }
        );
    }

    async checkCode() {
        // avoid making users click save on the settings
        // and then clicking the confirm button to check the code
        await this._callConfigMethod("button_check_l10n_dk_nemhandel_verification_code", true);
    }

    async sendCode() {
        this.state.isSmsButtonDisabled = true;
        // don't allow spamming the button
        setTimeout(() => this.state.isSmsButtonDisabled = false, waitTime);
        await this._callConfigMethod("button_send_l10n_dk_nemhandel_verification_code", true);
    }

    async createUser() {
        await this._callConfigMethod("button_create_l10n_dk_nemhandel_proxy_user", true);
    }
}

registry.category("view_widgets").add("l10n_dk_nemhandel_settings_buttons", {
    component: NemhandelSettingsButtons,
});
