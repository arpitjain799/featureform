import Resource from "api/resources/Resource.js";
import TypesenseClient from "./Search.js";

export const testData = [
  {
    name: "User sample preferences",
    "default-variant": "first-variant",
    type: "Feature",
    "all-variants": ["first-variant", "normalized variant"],
    variants: {
      "first-variant": {
        "variant-name": "first-variant",
        dimensions: 3,
        created: "2020-08-09-0290499",
        owner: "Simba Khadder",
        visibility: "private",
        revision: "2020-08-10-39402409",
        tags: ["model2vec", "compressed"],
        description: "Vector generated based on user preferences",
      },
      "normalized variant": {
        "variant-name": "normalized variant",
        dimensions: 3,
        created: "2020-08-09-0290499",
        owner: "Simba Khadder",
        visibility: "private",
        revision: "2020-08-10-39402409",
        tags: ["model2vec", "compressed"],
        description: "Vector generated based on user preferences, normalized",
      },
    },
  },
];

export const providerLogos = Object.freeze({
  Redis: "/Redis_Logo.svg",
  BigQuery: "/google_bigquery-ar21.svg",
  "Apache Spark": "/Apache_Spark_logo.svg",
  PostgreSQL: "Postgresql_elephant.svg",
  Snowflake: "Snowflake_Logo.svg",
});

//replace these with environment variables
//environment variables MUST begin with REACT_APP_
//example: process.env.REACT_APP_API_URL
//Sterling replace the things on the right with process.env.REACT_APP_...

//these all have to be exposed externally via ingress or a node port
const API_URL = "http://localhost:8181";
export const PROMETHEUS_URL = "http://localhost:9090/";
const TYPESENSE_PORT = "8108";
const TYPESENSE_URL = "localhost";
const TYPESENSE_API_KEY = "xyz";

const local = false;

export default class ResourcesAPI {
  static typeSenseClient = new TypesenseClient(
    TYPESENSE_PORT,
    TYPESENSE_URL,
    TYPESENSE_API_KEY
  );
  checkStatus() {
    return fetch(API_URL, {
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((res) => {
        res.json().then((json_data) => ({ data: json_data }));
      })
      .catch((error) => {
        console.error(error);
      });
  }

  fetchResources(type) {
    var fetchAddress;
    let resourceType = Resource[type];
    if (local) {
      fetchAddress = `/data/lists/wine-data.json`;
    } else {
      fetchAddress = `${API_URL}${resourceType.urlPath}`;
    }
    if (process.env.REACT_APP_EMPTY_RESOURCE_VIEW === "true") {
      fetchAddress = "/data/lists/wine-data-empty.json";
    }
    return fetch(fetchAddress, {
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((res) =>
        res.json().then((json_data) => {
          if (local) {
            return { data: json_data[type] };
          } else {
            return { data: json_data };
          }
        })
      )
      .catch((error) => {
        console.error(error);
      });
  }

  fetchEntity(type, title) {
    var fetchAddress;
    if (local) {
      fetchAddress = "/data/" + type + "/" + title + ".json";
    } else {
      fetchAddress = `${API_URL}/${type}/${title}`;
    }

    return fetch(fetchAddress, {
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((res) =>
        res.json().then((json_data) => {
          return { data: json_data };
        })
      )
      .catch((error) => {
        console.error(error);
      });
  }

  fetchSearch(query) {
    let typeSenseResults = this.constructor.typeSenseClient.search(query);
    return typeSenseResults.then((results) => {
      return results.results();
    });
  }

  fetchVariantSearchStub(query) {
    const fetchAddress = "/data/lists/search_results_example.json";

    return fetch(fetchAddress, {
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((res) => res.json().then((json_data) => ({ data: json_data })))
      .catch((error) => {
        console.error(error);
      });
  }
}
