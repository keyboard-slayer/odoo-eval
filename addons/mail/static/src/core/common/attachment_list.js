import { useState } from "@odoo/owl";

import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import { VideoAttachment } from "@mail/core/common/video_attachment";
import { AttachmentUtils } from "@mail/core/common/attachment_utils";

/**
 * @typedef {Object} Props
 * @property {import("models").Attachment[]} attachments
 * @property {number} imagesHeight
 * @property {ReturnType<import('@mail/core/common/message_search_hook').useMessageSearch>} [messageSearch]
 * @extends {AttachmentUtils<Props, Env>}
 */
export class AttachmentList extends AttachmentUtils {
    static components = { VideoAttachment };
    static props = ["attachments", "imagesHeight", "messageSearch?"];
    static template = "mail.AttachmentList";

    setup() {
        super.setup();
        this.ui = useState(useService("ui"));
        // Arbitrary high value, this is effectively a max-width.
        this.imagesWidth = 1920;
        this.fileViewer = useFileViewer();
    }

    /**
     * @param {import("models").Attachment} attachment
     */
    getImageUrl(attachment) {
        if (attachment.uploading && attachment.tmpUrl) {
            return attachment.tmpUrl;
        }
        return url(attachment.urlRoute, {
            ...attachment.urlQueryParams,
            width: this.imagesWidth,
            height: this.props.imagesHeight,
        });
    }

    get images() {
        return this.props.attachments.filter((a) => a.isImage);
    }

    get videos() {
        return this.props.attachments.filter((a) => a.isVideo);
    }

    get cards() {
        return this.props.attachments.filter((a) => !a.isImage && !a.isVideo);
    }

    onImageLoaded() {
        this.env.onImageLoaded?.();
    }

    get isInChatWindowAndIsAlignedRight() {
        return this.env.inChatWindow && this.env.alignedRight;
    }

    get isInChatWindowAndIsAlignedLeft() {
        return this.env.inChatWindow && !this.env.alignedRight;
    }

    get showDelete() {
        // in the composer they should all be implicitly deletable
        if (this.env.inComposer) {
            return true;
        }
        if (!this.attachment.isDeletable) {
            return false;
        }
        // in messages users are expected to delete the message instead of just the attachment
        return (
            !this.env.message ||
            this.env.message.hasTextContent ||
            (this.env.message && this.props.attachments.length > 1)
        );
    }
}
