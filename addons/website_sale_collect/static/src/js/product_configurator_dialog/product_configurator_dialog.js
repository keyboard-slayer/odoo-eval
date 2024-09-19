import {patch} from '@web/core/utils/patch';
import {
    ProductConfiguratorDialog
} from '@sale/js/product_configurator_dialog/product_configurator_dialog';

patch(ProductConfiguratorDialog, {
    props: {
        ...ProductConfiguratorDialog.props,
        clickAndCollectActive: {type: Boolean, optional: true},
    },
});

patch(ProductConfiguratorDialog.prototype, {
    /**
     * Allow adding to cart when click and collect is activated.
     *
     * @override of `website_sale`
     */
    _isQuantityAllowed(product, quantity) {
        return super._isQuantityAllowed(...arguments) || this.props.clickAndCollectActive;
    },
});
