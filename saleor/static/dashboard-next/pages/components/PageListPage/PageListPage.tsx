import Button from "@material-ui/core/Button";
import AddIcon from "@material-ui/icons/Add";
import * as React from "react";

import AppHeader from "../../../components/AppHeader";
import Container from "../../../components/Container";
import PageHeader from "../../../components/PageHeader";
import i18n from "../../../i18n";
import { ListActionProps, PageListProps } from "../../../types";
import { PageList_pages_edges_node } from "../../types/PageList";
import PageList from "../PageList/PageList";

export interface PageListPageProps
  extends PageListProps,
    ListActionProps<"onBulkDelete"> {
  pages: PageList_pages_edges_node[];
  onBack: () => void;
}

const PageListPage: React.StatelessComponent<PageListPageProps> = ({
  disabled,
  onAdd,
  onBack,
  onBulkDelete,
  onNextPage,
  onPreviousPage,
  onRowClick,
  pageInfo,
  pages
}) => (
  <Container>
    <AppHeader onBack={onBack}>{i18n.t("Configuration")}</AppHeader>
    <PageHeader title={i18n.t("Pages")}>
      <Button
        disabled={disabled}
        onClick={onAdd}
        variant="contained"
        color="primary"
      >
        {i18n.t("Add page")}
        <AddIcon />
      </Button>
    </PageHeader>
    <PageList
      disabled={disabled}
      pages={pages}
      onBulkDelete={onBulkDelete}
      onNextPage={onNextPage}
      onPreviousPage={onPreviousPage}
      onRowClick={onRowClick}
      pageInfo={pageInfo}
    />
  </Container>
);
PageListPage.displayName = "PageListPage";
export default PageListPage;
