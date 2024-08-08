import { Component, useState, useEffect } from "@odoo/owl";
import { ProgressBar } from "./file_upload_toast";
import { useService } from "@web/core/utils/hooks";

export class UploadProgressManager extends Component {
    static template = "web.UploadProgressManager";
    static components = {
        ProgressBar,
    };

    static props = {
        close: { type: Function },
    };

    setup() {
        this.uploadService = useService("file_upload");
        this.state = useState(this.uploadService.fileProgressBar);
        this.abortUpload = this.abortUpload.bind(this);
        useEffect(() => {
            const handleBeforeUnload = (event) => {
                if (this.state.uploadInProgress) {
                    event.preventDefault();
                    event.returnValue = "";
                }
            };
            window.addEventListener("beforeunload", handleBeforeUnload);
            // Cleanup function to remove the event listener
            return () => {
                window.removeEventListener("beforeunload", handleBeforeUnload);
            };
        });
    }

    abortUpload(targetFile) {
        if (this.state.xhr && !targetFile.abortFileUpload) {
            delete this.state.files[targetFile.id];
            this.state.xhr.abort(); // Abort the upload
            targetFile.abortFileUpload = true;
            if (Object.keys(this.state.files).length === 0) {
                this.state.isVisible = false;
            }
        } else {
            targetFile.abortFileUpload = false;
        }
    }
}
