import { patch } from "@web/core/utils/patch";
import { useImportRecordsDropzoneOnExternalViews } from "@base_import/import_records_dropzone/import_records_dropzone_hook";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.archInfo?.canImportRecords) {
            useImportRecordsDropzoneOnExternalViews(this.rootRef);
        }
    }
});
