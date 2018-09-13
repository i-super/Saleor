import * as React from "react";

import {
  PartialMutationProviderProps,
  PartialMutationProviderRenderProps
} from "../..";
import { TypedVariantImageUnassignMutation } from "../mutations";
import {
  VariantImageUnassign,
  VariantImageUnassignVariables
} from "../types/VariantImageUnassign";

interface VariantImageUnassignProviderProps
  extends PartialMutationProviderProps {
  children: PartialMutationProviderRenderProps<
    VariantImageUnassign,
    VariantImageUnassignVariables
  >;
}

const VariantImageUnassignProvider: React.StatelessComponent<
  VariantImageUnassignProviderProps
> = ({ children, onError, onSuccess }) => (
  <TypedVariantImageUnassignMutation onCompleted={onSuccess} onError={onError}>
    {(mutate, { data, loading, error }) => {
      return children({
        data,
        error,
        loading,
        mutate
      });
    }}
  </TypedVariantImageUnassignMutation>
);

export default VariantImageUnassignProvider;
