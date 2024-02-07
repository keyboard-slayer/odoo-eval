/* @odoo-module */

import { Record } from "@mail/core/common/record";
import { _t } from "@web/core/l10n/translation";

export class LivechatChannel extends Record {
    static id = "id";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
    /** @type {boolean} */
    hasSelfAsMember;
    discussChannels = Record.many("Thread", { inverse: "livechatChannel" });

    async leave() {
        await this._store.env.services.orm.call("im_livechat.channel", "action_quit", [this.id]);
        this._store.env.services.notification.add(_t("You left %s.", this.name), { type: "info" });
    }

    async join() {
        await this._store.env.services.orm.call("im_livechat.channel", "action_join", [this.id]);
        this._store.env.services.notification.add(_t("You joined %s.", this.name), {
            type: "info",
        });
    }
}
LivechatChannel.register();
