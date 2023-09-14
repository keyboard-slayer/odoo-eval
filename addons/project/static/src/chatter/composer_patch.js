import { Composer } from "@mail/core/common/composer";

import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    postData(composer) {
        const postData = super.postData(composer);
        if (this.env.projectSharingId) {
            postData.options.portal_security = {
                ...postData.options.portal_security,
                sharing_id: this.env.projectSharingId,
            };
        }
        return postData;
    },
});
