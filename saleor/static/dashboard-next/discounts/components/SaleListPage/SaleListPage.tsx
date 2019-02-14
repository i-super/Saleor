import Button from "@material-ui/core/Button";
import AddIcon from "@material-ui/icons/Add";
import * as React from "react";

import Container from "../../../components/Container";
import PageHeader from "../../../components/PageHeader";
import i18n from "../../../i18n";
import { PageListProps } from "../../../types";
import { SaleList_sales_edges_node } from "../../types/SaleList";
import SaleList from "../SaleList/SaleList";

export interface SaleListPageProps extends PageListProps {
  defaultCurrency: string;
  sales: SaleList_sales_edges_node[];
}

const SaleListPage: React.StatelessComponent<SaleListPageProps> = ({
  defaultCurrency,
  disabled,
  onAdd,
  onNextPage,
  onPreviousPage,
  onRowClick,
  pageInfo,
  sales
}) => (
  <Container width="md">
    <PageHeader title={i18n.t("Sales")}>
      <Button onClick={onAdd} variant="contained" color="secondary">
        {i18n.t("Add sale")}
        <AddIcon />
      </Button>
    </PageHeader>
    <SaleList
      defaultCurrency={defaultCurrency}
      disabled={disabled}
      onNextPage={onNextPage}
      onPreviousPage={onPreviousPage}
      onRowClick={onRowClick}
      pageInfo={pageInfo}
      sales={sales}
    />
  </Container>
);
SaleListPage.displayName = "SaleListPage";
export default SaleListPage;
