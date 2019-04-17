import DialogContentText from "@material-ui/core/DialogContentText";
import { stringify as stringifyQs } from "qs";
import * as React from "react";

import ActionDialog from "../../components/ActionDialog";
import { createPaginationState } from "../../components/Paginator";
import useNavigator from "../../hooks/useNavigator";
import useNotifier from "../../hooks/useNotifier";
import usePaginator from "../../hooks/usePaginator";
import i18n from "../../i18n";
import { getMutationState, maybe } from "../../misc";
import { StockAvailability } from "../../types/globalTypes";
import ProductListCard from "../components/ProductListCard";
import { getTabName } from "../misc";
import { TypedProductBulkDeleteMutation } from "../mutations";
import { TypedProductListQuery } from "../queries";
import { productBulkDelete } from "../types/productBulkDelete";
import {
  productAddUrl,
  productListUrl,
  ProductListUrlDialog,
  ProductListUrlFilters,
  ProductListUrlQueryParams,
  productUrl
} from "../urls";

interface ProductListProps {
  params: ProductListUrlQueryParams;
}

const PAGINATE_BY = 20;

export const ProductList: React.StatelessComponent<ProductListProps> = ({
  params
}) => {
  const navigate = useNavigator();
  const notify = useNotifier();
  const paginate = usePaginator();

  const closeModal = () =>
    navigate(
      productListUrl({
        ...params,
        action: undefined,
        ids: undefined
      }),
      true
    );

  const changeFilters = (filters: ProductListUrlFilters) =>
    navigate(productListUrl(filters));

  const openModal = (action: ProductListUrlDialog, ids: string[]) =>
    navigate(
      productListUrl({
        ...params,
        action,
        ids
      })
    );

  const paginationState = createPaginationState(PAGINATE_BY, params);

  return (
    <TypedProductListQuery
      displayLoader
      variables={{
        ...paginationState,
        stockAvailability: params.status
      }}
    >
      {({ data, loading, refetch }) => {
        const currentTab = getTabName(params);
        const { loadNextPage, loadPreviousPage, pageInfo } = paginate(
          maybe(() => data.products.pageInfo),
          paginationState,
          params
        );

        const handleBulkDelete = (data: productBulkDelete) => {
          if (data.productBulkDelete.errors.length === 0) {
            closeModal();
            notify({
              text: i18n.t("Products removed")
            });
            refetch();
          }
        };

        return (
          <TypedProductBulkDeleteMutation onCompleted={handleBulkDelete}>
            {(productBulkDelete, productBulkDeleteOpts) => {
              const bulkDeleteMutationState = getMutationState(
                productBulkDeleteOpts.called,
                productBulkDeleteOpts.loading,
                maybe(() => productBulkDeleteOpts.data.productBulkDelete.errors)
              );

              return (
                <>
                  <ProductListCard
                    currentTab={currentTab}
                    filtersList={[]}
                    onAdd={() => navigate(productAddUrl)}
                    disabled={loading}
                    products={
                      data &&
                      data.products !== undefined &&
                      data.products !== null
                        ? data.products.edges.map(p => p.node)
                        : undefined
                    }
                    onNextPage={loadNextPage}
                    onPreviousPage={loadPreviousPage}
                    pageInfo={pageInfo}
                    onRowClick={id => () => navigate(productUrl(id))}
                    onAllProducts={() =>
                      changeFilters({
                        status: undefined
                      })
                    }
                    onCustomFilter={() => undefined}
                    onAvailable={() =>
                      changeFilters({
                        status: StockAvailability.IN_STOCK
                      })
                    }
                    onOfStock={() =>
                      changeFilters({
                        status: StockAvailability.OUT_OF_STOCK
                      })
                    }
                    onBulkDelete={ids => openModal("delete", ids)}
                    onBulkPublish={ids => openModal("publish", ids)}
                    onBulkUnpublish={ids => openModal("unpublish", ids)}
                  />
                  <ActionDialog
                    open={params.action === "delete"}
                    confirmButtonState={bulkDeleteMutationState}
                    onClose={closeModal}
                    onConfirm={() =>
                      productBulkDelete({ variables: { ids: params.ids } })
                    }
                    title={i18n.t("Remove products")}
                    variant="delete"
                  >
                    <DialogContentText
                      dangerouslySetInnerHTML={{
                        __html: i18n.t(
                          "Are you sure you want to remove <strong>{{ number }}</strong> products?",
                          {
                            number: maybe(
                              () => params.ids.length.toString(),
                              "..."
                            )
                          }
                        )
                      }}
                    />
                  </ActionDialog>
                  <ActionDialog
                    open={params.action === "publish"}
                    confirmButtonState={"default"}
                    onClose={closeModal}
                    onConfirm={() => console.log(params.ids)}
                    title={i18n.t("Publish products")}
                  >
                    <DialogContentText
                      dangerouslySetInnerHTML={{
                        __html: i18n.t(
                          "Are you sure you want to publish <strong>{{ number }}</strong> products?",
                          {
                            number: maybe(
                              () => params.ids.length.toString(),
                              "..."
                            )
                          }
                        )
                      }}
                    />
                  </ActionDialog>
                  <ActionDialog
                    open={params.action === "unpublish"}
                    confirmButtonState={"default"}
                    onClose={closeModal}
                    onConfirm={() => console.log(params.ids)}
                    title={i18n.t("Unpublish products")}
                  >
                    <DialogContentText
                      dangerouslySetInnerHTML={{
                        __html: i18n.t(
                          "Are you sure you want to unpublish <strong>{{ number }}</strong> products?",
                          {
                            number: maybe(
                              () => params.ids.length.toString(),
                              "..."
                            )
                          }
                        )
                      }}
                    />
                  </ActionDialog>
                </>
              );
            }}
          </TypedProductBulkDeleteMutation>
        );
      }}
    </TypedProductListQuery>
  );
};
export default ProductList;
