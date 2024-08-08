import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { ProgressBar } from "@web/core/file_upload/file_upload_toast";

export class UploadProgressToast extends Component {
    static template = "html_editor.UploadProgressToast";
    static components = {
        ProgressBar,
    };
    static props = {
        close: Function,
    };

    setup() {
        this.uploadService = useService("upload");
        this.state = useState(this.uploadService.progressToast);
    }
}
