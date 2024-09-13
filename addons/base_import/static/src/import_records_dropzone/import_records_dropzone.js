import { Component } from "@odoo/owl";
import { Dropzone } from "@web/core/dropzone/dropzone";

export class ImportRecordsDropzone extends Component {
    static template = "base_import.ImportRecordsDropzone";
    static components = { Dropzone };
    static props = {
        ref: Object,
        resModel: { type: String },
    };
}
