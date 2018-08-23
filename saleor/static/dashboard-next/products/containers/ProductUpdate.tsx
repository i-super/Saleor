import * as React from "react";

import {
  PartialMutationProviderProps,
  PartialMutationProviderRenderProps
} from "../..";
import {
  ProductUpdateMutation,
  ProductUpdateMutationVariables
} from "../../gql-types";
import { TypedProductUpdateMutation } from "../mutations";

interface ProductUpdateProviderProps
  extends PartialMutationProviderProps<ProductUpdateMutation> {
  productId: string;
  children: PartialMutationProviderRenderProps<
    ProductUpdateMutation,
    ProductUpdateMutationVariables
  >;
}

const ProductUpdateProvider: React.StatelessComponent<
  ProductUpdateProviderProps
> = ({ productId, children, onError, onSuccess }) => (
  <TypedProductUpdateMutation onCompleted={onSuccess} onError={onError}>
    {(mutate, { data, error, loading }) =>
      children({
        data,
        error,
        loading,
        mutate
      })
    }
  </TypedProductUpdateMutation>
);

export default ProductUpdateProvider;
