import { Messaging } from "@mail/core/common/messaging_service";

import { patch } from "@web/core/utils/patch";

patch(Messaging.prototype, {
    async initialize() {
        if (!this.initMessagingParams.init_messaging.channel_types) {
            this.isReady.resolve();
            return;
        }
        return super.initialize();
    },
});
