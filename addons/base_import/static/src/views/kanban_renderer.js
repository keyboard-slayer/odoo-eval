import { patch } from "@web/core/utils/patch";
import { useImportRecordsDropzoneOnExternalViews } from "@base_import/import_records_dropzone/import_records_dropzone_hook";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

patch(KanbanRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.archInfo?.canImportRecords) {
            useImportRecordsDropzoneOnExternalViews(this.rootRef);
        }
    }
});
