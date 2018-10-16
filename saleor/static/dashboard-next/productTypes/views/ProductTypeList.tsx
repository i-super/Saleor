import * as React from "react";

import {
  productTypeAddUrl,
  productTypeDetailsUrl,
  productTypeListUrl
} from "..";
import ErrorMessageCard from "../../components/ErrorMessageCard";
import Navigator from "../../components/Navigator";
import { createPaginationData, createPaginationState, maybe } from "../../misc";
import ProductTypeListPage from "../components/ProductTypeListPage";
import { TypedProductTypeListQuery } from "../queries";

interface ProductTypeListProps {
  params: {
    after?: string;
    before?: string;
  };
}

const PAGINATE_BY = 20;

export const ProductTypeList: React.StatelessComponent<
  ProductTypeListProps
> = ({ params }) => (
  <Navigator>
    {navigate => {
      const paginationState = createPaginationState(PAGINATE_BY, params);
      return (
        <TypedProductTypeListQuery variables={paginationState}>
          {({ data, loading, error }) => {
            if (error) {
              return <ErrorMessageCard message="Something went wrong" />;
            }
            const {
              loadNextPage,
              loadPreviousPage,
              pageInfo
            } = createPaginationData(
              navigate,
              paginationState,
              productTypeListUrl,
              data && data.productTypes
                ? data.productTypes.pageInfo
                : undefined,
              loading
            );
            return (
              <ProductTypeListPage
                disabled={loading}
                productTypes={maybe(() =>
                  data.productTypes.edges.map(edge => edge.node)
                )}
                pageInfo={pageInfo}
                onAdd={() => navigate(productTypeAddUrl)}
                onNextPage={loadNextPage}
                onPreviousPage={loadPreviousPage}
                onRowClick={id => () => navigate(productTypeDetailsUrl(id))}
              />
            );
          }}
        </TypedProductTypeListQuery>
      );
    }}
  </Navigator>
);
ProductTypeList.displayName = "ProductTypeList";
export default ProductTypeList;
