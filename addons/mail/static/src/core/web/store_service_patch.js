import { Record } from "@mail/core/common/record";
import { Store } from "@mail/core/common/store_service";
import { compareDatetime } from "@mail/utils/common/misc";
import { _t } from "@web/core/l10n/translation";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Store} */
const StorePatch = {
    setup() {
        super.setup(...arguments);
        this.activityCounter = 0;
        this.activity_counter_bus_id = 0;
        this.activityGroups = Record.attr([], {
            onUpdate() {
                this.onUpdateActivityGroups();
            },
            sort(g1, g2) {
                /**
                 * Sort by model ID ASC but always place the activity group for "mail.activity" model at
                 * the end (other activities).
                 */
                const getSortId = (activityGroup) =>
                    activityGroup.model === "mail.activity" ? Number.MAX_VALUE : activityGroup.id;
                return getSortId(g1) - getSortId(g2);
            },
        });
    },
    onStarted() {
        super.onStarted(...arguments);
        this.env.services["multi_tab"].bus.addEventListener(
            "mail.activity/insert",
            ({ detail }) => {
                this.store.Activity.insert(detail, { broadcast: false, html: true });
            }
        );
        this.env.services["multi_tab"].bus.addEventListener(
            "mail.activity/delete",
            ({ detail }) => {
                const activity = this.store.Activity.insert(detail, { broadcast: false });
                activity.delete({ broadcast: false });
            }
        );
        this.env.services["multi_tab"].bus.addEventListener(
            "mail.activity/reload_chatter",
            ({ detail }) => {
                const thread = this.store.Thread.insert({
                    model: detail.model,
                    id: detail.id,
                });
                thread.fetchNewMessages();
            }
        );
    },
    get initMessagingParams() {
        return {
            ...super.initMessagingParams,
            failures: true,
            systray_get_activities: true,
        };
    },
    getNeedactionChannels() {
        return this.getRecentChannels().filter((channel) => channel.importantCounter > 0);
    },
    getRecentChannels() {
        return Object.values(this.Thread.records)
            .filter((thread) => thread.model === "discuss.channel")
            .sort((a, b) => compareDatetime(b.lastInterestDt, a.lastInterestDt) || b.id - a.id);
    },
    onUpdateActivityGroups() {},
    async scheduleActivity(resModel, resIds, defaultActivityTypeId = undefined) {
        const context = {
            active_model: resModel,
            active_ids: resIds,
            active_id: resIds[0],
            ...(defaultActivityTypeId !== undefined
                ? { default_activity_type_id: defaultActivityTypeId }
                : {}),
        };
        return new Promise((resolve) =>
            this.env.services.action.doAction(
                {
                    type: "ir.actions.act_window",
                    name:
                        resIds && resIds.length > 1
                            ? _t("Schedule Activity On Selected Records")
                            : _t("Schedule Activity"),
                    res_model: "mail.activity.schedule",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context,
                },
                { onClose: resolve }
            )
        );
    },
};
patch(Store.prototype, StorePatch);
