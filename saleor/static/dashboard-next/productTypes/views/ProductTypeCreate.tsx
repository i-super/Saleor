import * as React from "react";
import Navigator from "../../components/Navigator";

import { productTypeDetailsUrl, productTypeListUrl } from "..";
import Messages from "../../components/messages";
import i18n from "../../i18n";
import ProductTypeDetailsPage, {
  ProductTypeForm
} from "../components/ProductTypeDetailsPage";
import { AttributeSearchProvider } from "../containers/AttributeSearch";
import { TypedProductTypeCreateMutation } from "../mutations";
import { ProductTypeCreate as ProductTypeCreateMutation } from "../types/ProductTypeCreate";

const formData = {
  hasVariants: false,
  isShippingRequired: false,
  name: "",
  productAttributes: [],
  taxRate: undefined,
  variantAttributes: []
};

export const ProductTypeCreate: React.StatelessComponent = () => (
  <Messages>
    {pushMessage => (
      <Navigator>
        {navigate => (
          <AttributeSearchProvider>
            {(searchAttribute, searchState) => {
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
                <TypedProductTypeCreateMutation
                  onCompleted={handleCreateSuccess}
                >
                  {(
                    createProductType,
                    { loading: loadingCreate, data: createProductTypeData }
                  ) => {
                    const handleCreate = (formData: ProductTypeForm) =>
                      createProductType({
                        variables: {
                          input: {
                            ...formData,
                            productAttributes: formData.productAttributes.map(
                              choice => choice.value
                            ),
                            variantAttributes: formData.variantAttributes.map(
                              choice => choice.value
                            )
                          }
                        }
                      });
                    return (
                      <ProductTypeDetailsPage
                        disabled={loadingCreate}
                        errors={
                          createProductTypeData
                            ? createProductTypeData.productTypeCreate.errors
                            : undefined
                        }
                        pageTitle={i18n.t("Create Product Type", {
                          context: "page title"
                        })}
                        productType={formData}
                        productAttributes={[]}
                        variantAttributes={[]}
                        saveButtonBarState={
                          loadingCreate ? "loading" : "default"
                        }
                        searchLoading={
                          searchState ? searchState.loading : false
                        }
                        searchResults={
                          searchState &&
                          searchState.data &&
                          searchState.data.attributes
                            ? searchState.data.attributes.edges.map(
                                edge => edge.node
                              )
                            : []
                        }
                        onAttributeSearch={searchAttribute}
                        onBack={() => navigate(productTypeListUrl)}
                        onSubmit={handleCreate}
                      />
                    );
                  }}
                </TypedProductTypeCreateMutation>
              );
            }}
          </AttributeSearchProvider>
        )}
      </Navigator>
    )}
  </Messages>
);
export default ProductTypeCreate;
