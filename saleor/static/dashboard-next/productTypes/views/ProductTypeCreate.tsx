import * as React from "react";
import Navigator from "../../components/Navigator";

import { productTypeDetailsUrl, productTypeListUrl } from "..";
import Messages from "../../components/messages";
import i18n from "../../i18n";
import { maybe } from "../../misc";
import ProductTypeCreatePage, {
  ProductTypeForm
} from "../components/ProductTypeCreatePage";
import { TypedProductTypeCreateMutation } from "../mutations";
import { TypedProductTypeCreateDataQuery } from "../queries";
import { ProductTypeCreate as ProductTypeCreateMutation } from "../types/ProductTypeCreate";

export const ProductTypeCreate: React.StatelessComponent = () => (
  <Messages>
    {pushMessage => (
      <Navigator>
        {navigate => {
          const handleCreateSuccess = (
            updateData: ProductTypeCreateMutation
          ) => {
            if (updateData.productTypeCreate.errors.length === 0) {
              pushMessage({
                text: i18n.t("Successfully created product type")
              });
              navigate(
                productTypeDetailsUrl(
                  updateData.productTypeCreate.productType.id
                )
              );
            }
          };
          return (
            <TypedProductTypeCreateMutation onCompleted={handleCreateSuccess}>
              {(
                createProductType,
                { loading: loadingCreate, data: createProductTypeData }
              ) => {
                const handleCreate = (formData: ProductTypeForm) =>
                  createProductType({
                    variables: {
                      input: {
                        hasVariants: false,
                        isShippingRequired: formData.isShippingRequired,
                        name: formData.name,
                        taxRate: formData.chargeTaxes ? formData.taxRate : null,
                        weight: formData.weight
                      }
                    }
                  });
                return (
                  <TypedProductTypeCreateDataQuery>
                    {({ data, loading }) => (
                      <ProductTypeCreatePage
                        defaultWeightUnit={maybe(
                          () => data.shop.defaultWeightUnit
                        )}
                        disabled={loadingCreate || loading}
                        errors={
                          createProductTypeData
                            ? createProductTypeData.productTypeCreate.errors
                            : undefined
                        }
                        pageTitle={i18n.t("Create Product Type", {
                          context: "page title"
                        })}
                        saveButtonBarState={
                          loadingCreate ? "loading" : "default"
                        }
                        onBack={() => navigate(productTypeListUrl)}
                        onSubmit={handleCreate}
                      />
                    )}
                  </TypedProductTypeCreateDataQuery>
                );
              }}
            </TypedProductTypeCreateMutation>
          );
        }}
      </Navigator>
    )}
  </Messages>
);
export default ProductTypeCreate;
