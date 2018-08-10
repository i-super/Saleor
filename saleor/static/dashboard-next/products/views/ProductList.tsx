import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

import { productShowUrl } from "..";
import ErrorMessageCard from "../../components/ErrorMessageCard";
import Navigator from "../../components/Navigator";
import Toggle from "../../components/Toggle";
import ProductListCard from "../components/ProductListCard";
import { productListQuery, TypedProductListQuery } from "../queries";

interface ProductListProps {
  filters: any;
}

const decorate = withStyles(theme => ({
  root: {
    display: "grid",
    gridGap: theme.spacing.unit + "px",
    gridTemplateColumns: "100%",
    [theme.breakpoints.up("md")]: {
      gridGap: theme.spacing.unit * 2 + "px",
      // TODO: Check on firefox
      gridTemplateColumns: "3fr 1fr"
    }
  }
}));
export const ProductList = decorate<ProductListProps>(
  ({ classes, filters }) => (
    <div className={classes.root}>
      <Navigator>
        {navigate => {
          return (
            <Toggle>
              {(
                filtersVisible,
                { disable: hideFilters, enable: showFilters }
              ) => (
                <TypedProductListQuery
                  query={productListQuery}
                  variables={{ first: 12 }}
                  fetchPolicy="network-only"
                >
                  {({ data, loading, error, fetchMore }) => {
                    if (error) {
                      return (
                        <ErrorMessageCard message="Something went wrong" />
                      );
                    }
                    const loadNextPage = () => {
                      if (loading) {
                        return;
                      }
                      return fetchMore({
                        updateQuery: (previousResult, { fetchMoreResult }) => {
                          return {
                            ...fetchMoreResult,
                            products: {
                              ...fetchMoreResult.products,
                              pageInfo: {
                                ...fetchMoreResult.products.pageInfo,
                                hasPreviousPage: true
                              }
                            }
                          };
                        },
                        variables: {
                          after: data.products.pageInfo.endCursor,
                          first: 12
                        }
                      });
                    };
                    const loadPreviousPage = () => {
                      if (loading) {
                        return;
                      }
                      return fetchMore({
                        updateQuery: (
                          previousResult,
                          { fetchMoreResult, variables }
                        ) => {
                          return {
                            ...fetchMoreResult,
                            products: {
                              ...fetchMoreResult.products,
                              pageInfo: {
                                ...fetchMoreResult.products.pageInfo,
                                hasNextPage: true
                              }
                            }
                          };
                        },
                        variables: {
                          before: data.products.pageInfo.startCursor,
                          first: undefined,
                          last: 12
                        }
                      });
                    };
                    return (
                      <>
                        <div>
                          <ProductListCard
                            products={
                              data &&
                              data.products !== undefined &&
                              data.products !== null
                                ? data.products.edges.map(p => p.node)
                                : undefined
                            }
                            onFilter={showFilters}
                            onNextPage={loadNextPage}
                            onPreviousPage={loadPreviousPage}
                            hasPreviousPage={
                              data && data.products && !loading
                                ? data.products.pageInfo.hasPreviousPage
                                : false
                            }
                            hasNextPage={
                              data && data.products && !loading
                                ? data.products.pageInfo.hasNextPage
                                : false
                            }
                            onRowClick={id => () =>
                              navigate(productShowUrl(id))}
                          />
                        </div>
                      </>
                    );
                  }}
                </TypedProductListQuery>
              )}
            </Toggle>
          );
        }}
      </Navigator>
    </div>
  )
);
export default ProductList;
