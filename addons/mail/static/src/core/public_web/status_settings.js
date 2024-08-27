import { Component, useRef, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { markEventHandled } from "@web/core/utils/misc";
import { Picker, usePicker } from "@mail/core/common/picker";

export class StatusSettings extends Component {
    static components = { Dropdown, DropdownItem, Picker };
    static props = ["close"];
    static template = "discuss.StatusSettings";

    setup() {
        this.orm = useService("orm");
        this.store = useState(useService("mail.store"));
        this.actionService = useService("action");
        this.emojiButton = useRef("emoji-button");
        this.customStatusInput = useRef("custom-status-input");
        this.picker = usePicker(this.pickerSettings);
        this.state = useState({
            customStatus: this.store.self.custom_status || "",
            resetAfter: "today",
        });
    }

    get pickerSettings() {
        return {
            anchor: this.customStatusInput,
            buttons: [this.emojiButton],
            pickers: { emoji: (emoji) => this.addEmoji(emoji) },
            position: "bottom-start",
        };
    }

    addEmoji(str) {
        this.state.customStatus += str;
    }

    onClickViewProfile() {
        const action = {
            res_id: this.store.self.id,
            res_model: "res.partner",
            type: "ir.actions.act_window",
            views: [[false, "form"]],
        };
        this.actionService.doAction(action);
    }

    async setStatus(to) {
        rpc("/mail/im_status", { action: to });
        rpc("/discuss/settings/mute", { minutes: to == "do_not_disturb" ? -1 : false });
        this.store.self.im_status = to;
    }

    onClickAddEmoji(ev) {
        markEventHandled(ev, "Composer.onClickAddEmoji");
    }

    onConfirm() {
        rpc("/mail/custom_status", {
            custom_status: this.state.customStatus,
            reset_after: this.state.resetAfter,
        });
        this.store.self.custom_status = this.state.customStatus;
        this.props.close();
    }

    onClear() {
        this.state.customStatus = "";
        rpc("/mail/custom_status", { custom_status: "", reset_after: "never" });
        this.store.self.custom_status = "";
    }
}
