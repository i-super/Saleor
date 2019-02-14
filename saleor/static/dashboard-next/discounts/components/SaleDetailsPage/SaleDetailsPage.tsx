import * as React from "react";

import CardSpacer from "../../../components/CardSpacer";
import { ConfirmButtonTransitionState } from "../../../components/ConfirmButton";
import Container from "../../../components/Container";
import Form from "../../../components/Form";
import Grid from "../../../components/Grid";
import PageHeader from "../../../components/PageHeader";
import SaveButtonBar from "../../../components/SaveButtonBar";
import { Tab } from "../../../components/Tab";
import TabContainer from "../../../components/Tab/TabContainer";
import i18n from "../../../i18n";
import { maybe } from "../../../misc";
import { ListProps, UserError } from "../../../types";
import { SaleType } from "../../../types/globalTypes";
import { SaleDetails_sale } from "../../types/SaleDetails";
import SaleCategories from "../SaleCategories";
import SaleCollections from "../SaleCollections";
import SaleInfo from "../SaleInfo";
import SalePricing from "../SalePricing";
import SaleProducts from "../SaleProducts";
import SaleSummary from "../SaleSummary";

export interface FormData {
  name: string;
  startDate: string;
  endDate: string;
  value: string;
  type: SaleType;
}

export enum SaleDetailsPageTab {
  "categories",
  "collections",
  "products"
}

export interface SaleDetailsPageProps
  extends Pick<ListProps, Exclude<keyof ListProps, "onRowClick">> {
  activeTab: SaleDetailsPageTab;
  defaultCurrency: string;
  errors: UserError[];
  sale: SaleDetails_sale;
  saveButtonBarState: ConfirmButtonTransitionState;
  onBack: () => void;
  onCategoryAssign: () => void;
  onCategoryClick: (id: string) => () => void;
  onCollectionAssign: () => void;
  onCollectionClick: (id: string) => () => void;
  onProductAssign: () => void;
  onProductClick: (id: string) => () => void;
  onRemove: () => void;
  onSubmit: (data: FormData) => void;
  onTabClick: (index: SaleDetailsPageTab) => void;
}

const CategoriesTab = Tab(SaleDetailsPageTab.categories);
const CollectionsTab = Tab(SaleDetailsPageTab.collections);
const ProductsTab = Tab(SaleDetailsPageTab.products);

const SaleDetailsPage: React.StatelessComponent<SaleDetailsPageProps> = ({
  activeTab,
  defaultCurrency,
  disabled,
  errors,
  onRemove,
  onSubmit,
  onTabClick,
  pageInfo,
  sale,
  saveButtonBarState,
  onBack,
  onCategoryAssign,
  onCategoryClick,
  onCollectionAssign,
  onCollectionClick,
  onNextPage,
  onPreviousPage,
  onProductAssign,
  onProductClick
}) => {
  const initialForm: FormData = {
    endDate: maybe(() => sale.endDate),
    name: maybe(() => sale.name),
    startDate: maybe(() => sale.startDate),
    type: maybe(() => sale.type),
    value: maybe(() => sale.value.toString())
  };
  return (
    <Form errors={errors} initial={initialForm} onSubmit={onSubmit}>
      {({ change, data, errors: formErrors, hasChanged, submit }) => (
        <Container width="md">
          <PageHeader title={maybe(() => sale.name)} onBack={onBack} />
          <Grid>
            <div>
              <SaleInfo
                data={data}
                disabled={disabled}
                errors={formErrors}
                onChange={change}
              />
              <CardSpacer />
              <SalePricing
                data={data}
                defaultCurrency={defaultCurrency}
                disabled={disabled}
                errors={formErrors}
                onChange={change}
              />
              <CardSpacer />
              <TabContainer>
                <CategoriesTab
                  isActive={activeTab === SaleDetailsPageTab.categories}
                  changeTab={onTabClick}
                >
                  {i18n.t("Categories")}
                </CategoriesTab>
                <CollectionsTab
                  isActive={activeTab === SaleDetailsPageTab.collections}
                  changeTab={onTabClick}
                >
                  {i18n.t("Collections")}
                </CollectionsTab>
                <ProductsTab
                  isActive={activeTab === SaleDetailsPageTab.products}
                  changeTab={onTabClick}
                >
                  {i18n.t("Products")}
                </ProductsTab>
              </TabContainer>
              <CardSpacer />
              {activeTab === SaleDetailsPageTab.categories ? (
                <SaleCategories
                  disabled={disabled}
                  onCategoryAssign={onCategoryAssign}
                  onNextPage={onNextPage}
                  onPreviousPage={onPreviousPage}
                  onRowClick={onCategoryClick}
                  pageInfo={pageInfo}
                  sale={sale}
                />
              ) : activeTab === SaleDetailsPageTab.collections ? (
                <SaleCollections
                  disabled={disabled}
                  onCollectionAssign={onCollectionAssign}
                  onNextPage={onNextPage}
                  onPreviousPage={onPreviousPage}
                  onRowClick={onCollectionClick}
                  pageInfo={pageInfo}
                  sale={sale}
                />
              ) : (
                <SaleProducts
                  disabled={disabled}
                  onNextPage={onNextPage}
                  onPreviousPage={onPreviousPage}
                  onProductAssign={onProductAssign}
                  onRowClick={onProductClick}
                  pageInfo={pageInfo}
                  sale={sale}
                />
              )}
            </div>
            <div>
              <SaleSummary defaultCurrency={defaultCurrency} sale={sale} />
            </div>
          </Grid>
          <SaveButtonBar
            disabled={disabled || !hasChanged}
            onCancel={onBack}
            onDelete={onRemove}
            onSave={submit}
            state={saveButtonBarState}
          />
        </Container>
      )}
    </Form>
  );
};
SaleDetailsPage.displayName = "SaleDetailsPage";
export default SaleDetailsPage;
