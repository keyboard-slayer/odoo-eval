import { useService } from "@web/core/utils/hooks";

import { useRef, useState } from "@odoo/owl";
import { Attachment } from "@mail/core/common/attachment_model";
import { AttachmentUtils } from "@mail/core/common/attachment_utils";

export class VideoAttachment extends AttachmentUtils {
    static template = "mail.VideoAttachment";
    static props = {
        attachment: { type: Attachment },
        maxHeight: { type: Number },
        maxWidth: { type: Number },
        showDelete: { type: Function },
    };

    setup() {
        super.setup();
        this.store = useState(useService("mail.store"));
        this.state = useState({ paused: true });
        this.videoRefEl = useRef("videoRef");
    }

    onClickPlay() {
        if (this.videoRefEl.el && this.canPlay) {
            this.state.paused = false;
            this.videoRefEl.el.play();
            this.videoRefEl.el.setAttribute("controls", "controls");
        }
    }

    onPause() {
        if (this.videoRefEl.el) {
            this.state.paused = true;
            this.videoRefEl.el.removeAttribute("controls");
        }
    }

    get canPlay() {
        return !this.props.attachment.uploading && !this.env.inComposer;
    }
}
