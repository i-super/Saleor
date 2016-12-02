import React, { PropTypes } from 'react'
import ReactDOM from 'react-dom'
import Relay from 'react-relay'

import CategoryPage from './components/CategoryPage'
import ProductFilters from './components/ProductFilters'

const categoryPage = document.getElementById('category-page');
const categoryData = JSON.parse(categoryPage.getAttribute('data-category'));

Relay.injectNetworkLayer(
    new Relay.DefaultNetworkLayer('/graphql/', {
        credentials: 'same-origin',
    })
);

class App extends React.Component {

  static propTypes = {
    viewer: PropTypes.object
  }

  render() {
    return (
        <CategoryPage 
          category = {this.props.viewer.category}
          attributes = {this.props.viewer.attributes}
        />
      );
  }
}

const RelayApp = Relay.createContainer(App, {
  initialVariables: {
    categoryId: categoryData.id
  },
  fragments: {
    viewer: () => Relay.QL`
      fragment on Viewer {
        category(pk: $categoryId) {
          ${CategoryPage.getFragment('category')}
        }
        attributes {
          ${ProductFilters.getFragment('attributes')}
        }
      }
    `,
  },
});

const AppRoute = {
  queries: {
    viewer: () => Relay.QL`
      query { viewer }
    `,
  },
  params: {},
  name: 'Viewer',
};

ReactDOM.render(
  <Relay.RootContainer Component={RelayApp} route={AppRoute} />,
  categoryPage,
);
