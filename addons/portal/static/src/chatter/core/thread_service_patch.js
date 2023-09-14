import { ThreadService } from "@mail/core/common/thread_service";

import { patch } from "@web/core/utils/patch";

patch(ThreadService.prototype, {
    get chatterFetchRoute() {
        return "/mail/chatter_fetch";
    },
});
