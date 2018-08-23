import * as React from "react";

import {
  ProductImageReorderMutation,
  ProductImageReorderMutationVariables
} from "../../gql-types";
import { TypedProductImagesReorder } from "../mutations";

import {
  PartialMutationProviderProps,
  PartialMutationProviderRenderProps
} from "../..";

interface ProductImagesReorderProviderProps
  extends PartialMutationProviderProps<ProductImageReorderMutation> {
  productId: string;
  productImages: Array<{
    id: string;
    url: string;
  }>;
  children: PartialMutationProviderRenderProps<
    ProductImageReorderMutation,
    ProductImageReorderMutationVariables
  >;
}

const ProductImagesReorderProvider: React.StatelessComponent<
  ProductImagesReorderProviderProps
> = props => (
  <TypedProductImagesReorder
    onCompleted={props.onSuccess}
    onError={props.onError}
  >
    {(mutate, { data, error, loading }) =>
      props.children({
        data,
        error,
        loading,
        mutate: opts => {
          const productImagesMap = props.productImages.reduce((prev, curr) => {
            prev[curr.id] = curr;
            return prev;
          }, {});
          const productImages = opts.variables.imagesIds.map((id, index) => ({
            __typename: "ProductImage",
            ...productImagesMap[id],
            sortOrder: index
          }));
          const optimisticResponse = {
            productImageReorder: {
              __typename: "ProductImageReorder",
              errors: null,
              productImages
            }
          };
          return mutate({
            optimisticResponse,
            variables: opts.variables
          });
        }
      })
    }
  </TypedProductImagesReorder>
);

export default ProductImagesReorderProvider;
