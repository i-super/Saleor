import CssBaseline from "@material-ui/core/CssBaseline";
import MuiThemeProvider from "@material-ui/core/styles/MuiThemeProvider";
import * as React from "react";

import theme from "../theme";

export const Decorator = storyFn => (
  <MuiThemeProvider theme={theme}>
    <CssBaseline />
    {storyFn()}
  </MuiThemeProvider>
);
export default Decorator;
