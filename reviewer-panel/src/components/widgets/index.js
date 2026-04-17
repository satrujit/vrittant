import StockIndices from './StockIndices.jsx';
import CryptoPrices from './CryptoPrices.jsx';
import Commodities from './Commodities.jsx';
import CurrencyRates from './CurrencyRates.jsx';
import FiiDiiActivity from './FiiDiiActivity.jsx';
import RichestPeople from './RichestPeople.jsx';
import UpiStats from './UpiStats.jsx';
import FuelCombined from './FuelCombined.jsx';
import HundiCollection from './HundiCollection.jsx';
import OdishaTemps from './OdishaTemps.jsx';
import MetroWeather from './MetroWeather.jsx';
import Weather from './Weather.jsx';
import AirQuality from './AirQuality.jsx';
import SunMoon from './SunMoon.jsx';
import Earthquakes from './Earthquakes.jsx';
import NasaEonet from './NasaEonet.jsx';
import IplNext from './IplNext.jsx';
import IplRecent from './IplRecent.jsx';
import IplPointsTable from './IplPointsTable.jsx';
import IccFixtures from './IccFixtures.jsx';
import EplNext from './EplNext.jsx';
import F1LastRace from './F1LastRace.jsx';
import F1Standings from './F1Standings.jsx';
import IssNow from './IssNow.jsx';
import PeopleInSpace from './PeopleInSpace.jsx';
import SpacexNext from './SpacexNext.jsx';
import NasaApod from './NasaApod.jsx';
import GitaVerse from './GitaVerse.jsx';
import QuoteOfDay from './QuoteOfDay.jsx';
import WordOfDay from './WordOfDay.jsx';
import TodayInHistory from './TodayInHistory.jsx';
import WikiFeatured from './WikiFeatured.jsx';
import WikiOnThisDay from './WikiOnThisDay.jsx';
import TriviaQuestion from './TriviaQuestion.jsx';
import ChessPuzzle from './ChessPuzzle.jsx';
import SudokuPuzzle from './SudokuPuzzle.jsx';
import UpcomingMovies from './UpcomingMovies.jsx';
import NewYearCountdown from './NewYearCountdown.jsx';

/**
 * Map widget kind → renderer Component.
 * Each component receives `{ data, allWidgets }` props (only `fuel_combined`
 * uses `allWidgets`, since it composes 3 separate snapshots).
 *
 * To add a new widget kind: create one file under this folder, then add one
 * entry below.
 */
export const CATALOG = {
  // Markets
  stock_indices: StockIndices,
  fii_dii_activity: FiiDiiActivity,
  commodities: Commodities,
  crypto_prices: CryptoPrices,
  currency_rates: CurrencyRates,
  richest_people: RichestPeople,
  upi_stats: UpiStats,

  // Local
  fuel_combined: FuelCombined,
  hundi_collection: HundiCollection,
  odisha_temps: OdishaTemps,

  // Weather & Environment
  weather: Weather,
  metro_weather: MetroWeather,
  air_quality: AirQuality,
  sun_moon: SunMoon,
  earthquakes: Earthquakes,
  nasa_eonet: NasaEonet,

  // Sports
  ipl_next: IplNext,
  ipl_recent: IplRecent,
  ipl_points_table: IplPointsTable,
  icc_fixtures: IccFixtures,
  epl_next: EplNext,
  f1_last_race: F1LastRace,
  f1_standings: F1Standings,

  // Space
  iss_now: IssNow,
  people_in_space: PeopleInSpace,
  spacex_next: SpacexNext,
  nasa_apod: NasaApod,

  // Knowledge
  gita_verse: GitaVerse,
  quote_of_day: QuoteOfDay,
  word_of_day: WordOfDay,
  today_in_history: TodayInHistory,
  wiki_featured: WikiFeatured,
  wiki_on_this_day: WikiOnThisDay,
  trivia_question: TriviaQuestion,

  // Puzzles & Entertainment
  chess_puzzle: ChessPuzzle,
  sudoku_puzzle: SudokuPuzzle,
  upcoming_movies: UpcomingMovies,
  new_year_countdown: NewYearCountdown,
};
