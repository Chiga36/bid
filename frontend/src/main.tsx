import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { TenderProvider } from "./context/TenderContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <TenderProvider>
        <App />
      </TenderProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
