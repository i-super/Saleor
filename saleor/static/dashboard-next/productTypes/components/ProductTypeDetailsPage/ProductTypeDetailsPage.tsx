import DialogContentText from "@material-ui/core/DialogContentText";
import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

import ActionDialog from "../../../components/ActionDialog";
import Container from "../../../components/Container";
import { ControlledCheckbox } from "../../../components/ControlledCheckbox";
import Form from "../../../components/Form";
import PageHeader from "../../../components/PageHeader";
import SaveButtonBar, {
  SaveButtonBarState
} from "../../../components/SaveButtonBar";
import Toggle from "../../../components/Toggle";
import i18n from "../../../i18n";
import { maybe } from "../../../misc";
import {
  AttributeTypeEnum,
  TaxRateType,
  WeightUnitsEnum
} from "../../../types/globalTypes";
import { ProductTypeDetails_productType } from "../../types/ProductTypeDetails";
import ProductTypeAttributes from "../ProductTypeAttributes/ProductTypeAttributes";
import ProductTypeDetails from "../ProductTypeDetails/ProductTypeDetails";
import ProductTypeShipping from "../ProductTypeShipping/ProductTypeShipping";
import ProductTypeTaxes from "../ProductTypeTaxes/ProductTypeTaxes";

interface ChoiceType {
  label: string;
  value: string;
}
export interface ProductTypeForm {
  name: string;
  hasVariants: boolean;
  isShippingRequired: boolean;
  taxRate: TaxRateType;
  productAttributes: ChoiceType[];
  variantAttributes: ChoiceType[];
  weight: number;
}
export interface ProductTypeDetailsPageProps {
  errors: Array<{
    field: string;
    message: string;
  }>;
  productType: ProductTypeDetails_productType;
  defaultWeightUnit: WeightUnitsEnum;
  disabled: boolean;
  pageTitle: string;
  saveButtonBarState: SaveButtonBarState;
  onAttributeAdd: (type: AttributeTypeEnum) => void;
  onAttributeDelete: (id: string, event: React.MouseEvent<any>) => void;
  onAttributeUpdate: (id: string) => void;
  onBack: () => void;
  onDelete: () => void;
  onSubmit: (data: ProductTypeForm) => void;
}

const decorate = withStyles(theme => ({
  cardContainer: {
    marginTop: theme.spacing.unit * 2
  },
  root: {
    display: "grid" as "grid",
    gridColumnGap: theme.spacing.unit * 2 + "px",
    gridTemplateColumns: "2fr 1fr"
  }
}));
const ProductTypeDetailsPage = decorate<ProductTypeDetailsPageProps>(
  ({
    classes,
    defaultWeightUnit,
    disabled,
    errors,
    pageTitle,
    productType,
    saveButtonBarState,
    onAttributeAdd,
    onAttributeDelete,
    onAttributeUpdate,
    onBack,
    onDelete,
    onSubmit
  }) => {
    const formInitialData: ProductTypeForm = {
      hasVariants:
        maybe(() => productType.hasVariants) !== undefined
          ? productType.hasVariants
          : false,
      isShippingRequired:
        maybe(() => productType.isShippingRequired) !== undefined
          ? productType.isShippingRequired
          : false,
      name: maybe(() => productType.name) !== undefined ? productType.name : "",
      productAttributes:
        maybe(() => productType.productAttributes) !== undefined
          ? productType.productAttributes.map(attribute => ({
              label: attribute.name,
              value: attribute.id
            }))
          : [],
      taxRate:
        maybe(() => productType.taxRate) !== undefined
          ? productType.taxRate
          : null,
      variantAttributes:
        maybe(() => productType.variantAttributes) !== undefined
          ? productType.variantAttributes.map(attribute => ({
              label: attribute.name,
              value: attribute.id
            }))
          : [],
      weight: maybe(() => productType.weight.value)
    };
    return (
      <Toggle>
        {(openedDeleteDialog, { toggle: toggleDeleteDialog }) => (
          <>
            <Form
              errors={errors}
              initial={formInitialData}
              onSubmit={onSubmit}
              key={JSON.stringify(productType)}
            >
              {({ change, data, hasChanged, submit }) => (
                <Container width="md">
                  <PageHeader title={pageTitle} onBack={onBack} />
                  <div className={classes.root}>
                    <div>
                      <ProductTypeDetails
                        data={data}
                        disabled={disabled}
                        onChange={change}
                      />
                      <div className={classes.cardContainer}>
                        <ProductTypeAttributes
                          attributes={maybe(
                            () => productType.productAttributes
                          )}
                          type={AttributeTypeEnum.PRODUCT}
                          onAttributeAdd={onAttributeAdd}
                          onAttributeDelete={onAttributeDelete}
                          onAttributeUpdate={onAttributeUpdate}
                        />
                      </div>
                      <div className={classes.cardContainer}>
                        <ControlledCheckbox
                          checked={data.hasVariants}
                          disabled={disabled}
                          label={i18n.t("This product type has variants")}
                          name="hasVariants"
                          onChange={change}
                        />
                      </div>
                      {data.hasVariants && (
                        <div className={classes.cardContainer}>
                          <ProductTypeAttributes
                            attributes={maybe(
                              () => productType.variantAttributes
                            )}
                            type={AttributeTypeEnum.VARIANT}
                            onAttributeAdd={onAttributeAdd}
                            onAttributeDelete={onAttributeDelete}
                            onAttributeUpdate={onAttributeUpdate}
                          />
                        </div>
                      )}
                    </div>
                    <div>
                      <ProductTypeShipping
                        disabled={disabled}
                        data={data}
                        defaultWeightUnit={defaultWeightUnit}
                        onChange={change}
                      />
                      <div className={classes.cardContainer}>
                        <ProductTypeTaxes
                          disabled={disabled}
                          data={data}
                          onChange={change}
                        />
                      </div>
                    </div>
                  </div>
                  <SaveButtonBar
                    onCancel={onBack}
                    onDelete={toggleDeleteDialog}
                    onSave={submit}
                    disabled={disabled || !hasChanged}
                    state={saveButtonBarState}
                  />
                </Container>
              )}
            </Form>

            <ActionDialog
              open={openedDeleteDialog}
              onClose={toggleDeleteDialog}
              onConfirm={onDelete}
              title={i18n.t("Remove product type")}
              variant="delete"
            >
              <DialogContentText
                dangerouslySetInnerHTML={{
                  __html: i18n.t(
                    "Are you sure you want to remove <strong>{{ name }}</strong>?",
                    { name: maybe(() => productType.name) }
                  )
                }}
              />
            </ActionDialog>
          </>
        )}
      </Toggle>
    );
  }
);
ProductTypeDetailsPage.displayName = "ProductTypeDetailsPage";
export default ProductTypeDetailsPage;
