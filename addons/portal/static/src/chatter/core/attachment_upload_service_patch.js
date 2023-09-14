import { AttachmentUploadService } from "@mail/core/common/attachment_upload_service";

import { patch } from "@web/core/utils/patch";

patch(AttachmentUploadService.prototype, {
    _makeFormData(formData, file, hooker, tmpId, options) {
        super._makeFormData(...arguments);
        if (hooker.thread.model != "discuss.channel") {
            formData.append("name", file.name);
            formData.append("file", file);
        }
        return formData;
    },

    getUploadURL(threadModel) {
        if (threadModel != "discuss.channel") {
            return "/portal/attachment/add";
        }
        return super.getUploadURL(...arguments);
    },
});
